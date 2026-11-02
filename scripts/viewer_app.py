"""建筑采样 3D 预览桌面应用（customtkinter + matplotlib）+ 方块替换编辑。

界面按「浏览 / 生成 / 设计 / 编辑 / 工具」分区，中央始终保留 3D 预览。 浏览可切换样本目录（默认最新 design/*/npz）。
「设计」：截图 + 文字要求 → 推断风格/地形 → 条件生成。
「工具」：Phase1 分析、Phase3 相似、Phase4 红石模板、一键流水线。
"""
from __future__ import annotations

import os
import subprocess
import sys
import threading
import colorsys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

try:
    import customtkinter as ctk
except ImportError:  # pragma: no cover
    import tkinter as ctk  # type: ignore

import tkinter as tk
from tkinter import filedialog, messagebox

from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
from matplotlib.lines import Line2D
from matplotlib.figure import Figure
from matplotlib import font_manager, rcParams
from mpl_toolkits.mplot3d import Axes3D  # noqa: F401


def _setup_cn_font() -> None:
    """尽量让 matplotlib 标题/坐标显示中文（Windows 常见字体）。"""
    candidates = [
        "Microsoft YaHei",
        "SimHei",
        "Microsoft JhengHei",
        "Noto Sans CJK SC",
        "Source Han Sans SC",
        "Arial Unicode MS",
    ]
    available = {f.name for f in font_manager.fontManager.ttflist}
    for name in candidates:
        if name in available:
            rcParams["font.sans-serif"] = [name, "DejaVu Sans"]
            rcParams["axes.unicode_minus"] = False
            return
    rcParams["axes.unicode_minus"] = False


_setup_cn_font()

from src.app.sample_runner import (
    count_blocks,
    generate_samples,
    load_label_vocab,
    list_checkpoints,
    list_sample_files,
    load_voxel_npz,
    next_edit_path,
    project_root,
    replace_block_id,
    save_voxels_pair,
    short_block_name,
)
from src.app.design_brief import (
    DesignSpec,
    api_key_available,
    format_spec_for_ui,
    generate_from_design,
    infer_design_spec,
)
from src.app.mc_render import render_mc_voxels
from src.app.block_zh_cn import zh_name as block_zh_name
from src.app.build_steps import (
    STAGE_LABELS,
    STAGE_ORDER,
    apply_upto,
    compute_stages,
    stages_summary,
)
from src.app.thumbs import render_thumb, sample_stats
from src.app.furnish import furnish, furnish_summary
from src.app.restyle import STYLE_LABELS, restyle
from src.app.blueprint import build_from_image
from src.app.region_edit import apply_region_op, parse_instruction
from src.app.candidate_rank import rank_results
from src.app.floors import plan_interior as plan_floors
from src.app.floors import summary as floors_summary
from src.app.mc_textures import (
    ensure_textures,
    load_pil_icon,
    texture_status_line,
)  # UX_P1_TEXTURES
from src.app.viewer_voxel_tools import (
    BRUSH_PRESETS,
    TOOL_BREAK,
    TOOL_MOVE,
    TOOL_PAINT,
    TOOL_PLACE,
    TOOL_SELECT,
    UndoStack,
    VoxelClipboard,
    apply_box_fill,
    apply_break,
    apply_break_brush,
    apply_move,
    apply_paint,
    apply_paint_brush,
    apply_place,
    apply_place_brush,
    copy_region,
    cut_region,
    nudge,
    paste_region,
    pick_nearest_face,
    place_pos_from_face,
)
from src.data.export_litematic_util import export_voxels_to_companion, resolve_schematics_dir
from src.app.game_bridge import (
    build_step_card_text,
    copy_text_to_clipboard,
    detect_minecraft_running,
    list_schematics,
    open_in_explorer,
    write_last_export_sidecar,
)
from src.app.materials_bom import write_export_sidecars
from src.data.mc_versions import (
    DEFAULT_VERSION_ID,
    get_version,
    version_id_from_menu_label,
    version_menu_labels,
)
from src.utils import load_config, load_palette
from src.app.schemes import (
    create_scheme,
    export_scheme_litematic,
    import_litematic as scheme_import_litematic,
    list_schemes,
    load_scheme,
    save_scheme,
    schemes_root,
)
from tkinter import simpledialog


QUICK_TARGETS = [
    "minecraft:stone",
    "minecraft:cobblestone",
    "minecraft:oak_planks",
    "minecraft:oak_log",
    "minecraft:glass",
    "minecraft:bricks",
    "minecraft:dirt",
    "minecraft:grass_block",
    "minecraft:white_concrete",
    "minecraft:black_concrete",
    "minecraft:spruce_planks",
    "minecraft:dark_oak_planks",
]

# UX P0: bottom hotbar defaults (slots 1-9) — place/paint target
HOTBAR_DEFAULTS = [
    "minecraft:stone",
    "minecraft:cobblestone",
    "minecraft:oak_planks",
    "minecraft:oak_log",
    "minecraft:glass",
    "minecraft:bricks",
    "minecraft:dirt",
    "minecraft:grass_block",
    "minecraft:white_concrete",
]

MODE_BROWSE = "浏览"
MODE_GENERATE = "生成"
MODE_DESIGN = "设计"
MODE_EDIT = "编辑"
MODE_TOOLS = "工具"

# —— MCBlock 风格主题：深色石质 + 草绿强调 ——
MC_PANEL = "#242427"
MC_PANEL_LOW = "#1c1c1f"
MC_CARD = "#2d2d31"
MC_CARD_HOVER = "#37373c"
MC_CARD_ACTIVE = "#34482a"
MC_SLOT = "#35353a"
MC_BORDER = "#48484f"
MC_TEXT = "#e9e9ec"
MC_MUTED = "#9a9aa2"
MC_ACCENT = "#7cbf3f"
MC_ACCENT_HOVER = "#68a832"
MC_GOLD = "#e8c14a"

# 缩略图卡片尺寸（宽 x 高）
THUMB_W, THUMB_H = 104, 70

# 材质库默认展示的常用建筑方块
COMMON_MATERIALS = [
    "minecraft:stone",
    "minecraft:cobblestone",
    "minecraft:stone_bricks",
    "minecraft:smooth_stone",
    "minecraft:deepslate_bricks",
    "minecraft:oak_planks",
    "minecraft:spruce_planks",
    "minecraft:dark_oak_planks",
    "minecraft:oak_log",
    "minecraft:spruce_log",
    "minecraft:stripped_oak_log",
    "minecraft:glass",
    "minecraft:glass_pane",
    "minecraft:bricks",
    "minecraft:terracotta",
    "minecraft:white_terracotta",
    "minecraft:sandstone",
    "minecraft:red_sandstone",
    "minecraft:dirt",
    "minecraft:grass_block",
    "minecraft:moss_block",
    "minecraft:gravel",
    "minecraft:sand",
    "minecraft:white_concrete",
    "minecraft:light_gray_concrete",
    "minecraft:gray_concrete",
    "minecraft:black_concrete",
    "minecraft:brown_concrete",
    "minecraft:white_wool",
    "minecraft:black_wool",
    "minecraft:oak_leaves",
    "minecraft:spruce_leaves",
    "minecraft:oak_stairs",
    "minecraft:stone_brick_stairs",
    "minecraft:oak_slab",
    "minecraft:stone_brick_slab",
    "minecraft:oak_fence",
    "minecraft:oak_door",
]


def _font(size: int = 12, bold: bool = False) -> "ctk.CTkFont":
    """统一字体（中文优先 YaHei）。"""
    weight = "bold" if bold else "normal"
    try:
        return ctk.CTkFont(family="Microsoft YaHei", size=size, weight=weight)
    except Exception:
        return ctk.CTkFont(size=size, weight=weight)




def _count_listable_samples(out_dir: Path) -> int:
    """Count npz names that list_sample_files would accept (cheap glob+regex)."""
    return len(list_sample_files(out_dir))


def discover_sample_dirs(root: Path, *, limit: int = 24) -> list[tuple[str, Path]]:
    """Return (label, path) for browseable sample folders.

    Always includes config ``outputs/samples`` (if present). Then newest
    ``outputs/design/*/npz`` dirs that contain listable ``sample_*.npz``.
    Labels are short folder names with counts, e.g. ``pool_scaffold_… (8)``.
    """
    root = Path(root)
    seen: set[Path] = set()
    out: list[tuple[str, Path]] = []

    samples = root / "outputs" / "samples"
    if samples.is_dir():
        n = _count_listable_samples(samples)
        label = f"默认 samples ({n})" if n else "默认 samples"
        out.append((label, samples.resolve()))
        seen.add(samples.resolve())

    design = root / "outputs" / "design"
    if design.is_dir():
        candidates: list[tuple[float, Path, str]] = []
        for run in design.iterdir():
            if not run.is_dir():
                continue
            npz_dir = run / "npz"
            if not npz_dir.is_dir():
                continue
            n = _count_listable_samples(npz_dir)
            if n <= 0:
                continue
            try:
                mtime = npz_dir.stat().st_mtime
            except OSError:
                mtime = 0.0
            candidates.append((mtime, npz_dir.resolve(), run.name))
        candidates.sort(key=lambda t: t[0], reverse=True)
        for _mtime, npz_dir, run_name in candidates:
            if npz_dir in seen:
                continue
            seen.add(npz_dir)
            out.append((f"{run_name} ({_count_listable_samples(npz_dir)})", npz_dir))
            if len(out) >= limit:
                break
    return out


def latest_design_npz_dir(root: Path) -> Path | None:
    """Newest ``outputs/design/*/npz`` with listable samples, or None."""
    for label, path in discover_sample_dirs(root, limit=32):
        if "默认 samples" in label:
            continue
        return path
    return None


def _block_color(block_id: int) -> tuple[float, float, float, float]:
    if block_id <= 0:
        return (0.0, 0.0, 0.0, 0.0)
    h = ((block_id * 0.618033988749895) % 1.0)
    s = 0.55 + (block_id % 5) * 0.08
    v = 0.75 + (block_id % 3) * 0.08
    r, g, b = colorsys.hsv_to_rgb(h, min(s, 0.95), min(v, 0.95))
    return (r, g, b, 0.95)


def build_facecolors(
    voxels: np.ndarray, highlight_id: int | None = None
) -> tuple[np.ndarray, np.ndarray]:
    filled = voxels > 0
    colors = np.zeros(voxels.shape + (4,), dtype=np.float32)
    for bid in np.unique(voxels[filled]):
        colors[voxels == bid] = _block_color(int(bid))
    if highlight_id is not None and highlight_id > 0:
        mask = voxels == int(highlight_id)
        if mask.any():
            base = colors[mask]
            colors[mask] = np.clip(base * np.array([1.25, 1.25, 1.25, 1.0]) + 0.15, 0, 1)
    return filled, colors


class ViewerApp(ctk.CTk):
    def __init__(self, out_dir: str | Path | None = None) -> None:
        super().__init__()
        self.title("MC 建筑工作台 · 建筑库 / 预览 / 建模")
        self.geometry("1440x880")
        self.minsize(1200, 720)

        if hasattr(ctk, "set_appearance_mode"):
            ctk.set_appearance_mode("dark")
            try:
                ctk.set_default_color_theme("green")  # 草绿强调，贴近 MCBlock
            except Exception:
                ctk.set_default_color_theme("blue")

        self.root_dir = project_root()
        self.cfg = load_config(self.root_dir / "configs/default.yaml")
        self._batch_label_to_path: dict[str, Path] = {}
        if out_dir is not None:
            p = Path(out_dir)
            self.out_dir = p if p.is_absolute() else (self.root_dir / p)
        else:
            # Double-click / normal launch: prefer newest design batch so
            # pool_scaffold / full_style runs show up without --samples.
            latest = latest_design_npz_dir(self.root_dir)
            self.out_dir = latest if latest is not None else (
                self.root_dir / self.cfg["sample"]["out_dir"]
            )
        self.palette = load_palette(self.root_dir / self.cfg["data"]["palette_path"])
        self.name_to_id = {v: k for k, v in self.palette.items()}

        self.current_voxels: np.ndarray | None = None
        self.current_path: Path | None = None
        self._undo_stack = UndoStack(max_depth=32)
        self._dirty = False
        self._generating = False
        self._source_id: int | None = None
        self._block_buttons: list = []
        self._last_render_info: dict = {}
        # style_perf_var set below (default True for orbit)
        # Y-slice: show only voxels with y <= value (32 = full for 32^3).
        self.y_slice_var = tk.IntVar(value=32)
        self._mode = MODE_BROWSE
        self._design_image_path: Path | None = None
        self._last_design_spec: DesignSpec | None = None
        self._scheme_slug: str | None = None
        # MCBlock-like voxel tools + orbit LOD
        self._voxel_tool = TOOL_SELECT
        self._sel_pos: tuple[int, int, int] | None = None
        self._sel_corner_b: tuple[int, int, int] | None = None  # box second corner
        self._move_src: tuple[int, int, int] | None = None
        self._box_anchor: tuple[int, int, int] | None = None  # box-fill first click
        self._clipboard = VoxelClipboard()
        self._brush_radius = 0  # 0=1x1, 1=3x3x3, 2=5x5x5
        self._brush_shape = "cube"
        self._face_meta: list = []
        self._orbiting = False
        self._orbit_lod_active = False
        self._press_xy: tuple[float, float] | None = None
        self._did_drag = False
        self._draw_edges_var = tk.BooleanVar(value=False)
        # Default ON for snappier orbit on 3k-10k block houses (RTX 3050 laptop).
        self.style_perf_var = tk.BooleanVar(value=True)
        # UX P0 workbench: hotbar + crosshair
        self._hotbar_names: list[str] = list(HOTBAR_DEFAULTS)
        self._hotbar_slot: int = 0  # 0..8
        self._hotbar_buttons: list = []
        self._crosshair_artists: list = []
        self._crosshair_label = None
        self._hotbar_images: list = []
        self._texture_info: dict = {}
        self._toast_job = None
        self._press_button: int | None = None
        # UX P2: schemes list + export-to-game
        self._scheme_list_rows: list = []
        # UX P3: game bridge (schematics list / step card / MC detect)
        self._bridge_rows: list = []
        self._bridge_selected: str | None = None  # full path
        self._last_export_name: str | None = None
        self._bridge_auto_job = None
        self._bridge_auto_ms = 4000
        # 建筑库卡片 + 缩略图队列
        self._sample_cards: dict[Path, tuple] = {}
        self._thumb_queue: list[Path] = []
        self._card_images: list = []
        # 建造步骤条
        self._steps: list[dict] = []
        self._step_by_key: dict[str, int] = {}
        self._step_index: int | None = None
        self._steps_play_job = None
        self._mat_icons: list = []

        self._build_ui()
        self.refresh_lists()
        self._refresh_target_choices()
        try:
            self._refresh_scheme_list()
        except Exception:
            pass
        try:
            self._refresh_game_bridge()
            self._schedule_bridge_auto()
        except Exception:
            pass
        try:
            self._texture_info = ensure_textures()
            self._set_status(texture_status_line())
        except Exception as _tex_exc:  # noqa: BLE001
            self._texture_info = {"ok": False, "note": f"FALLBACK: {_tex_exc}"}
        self._switch_mode(MODE_BROWSE)
        self.after(200, self._autoload_first_sample)

    def _build_ui(self) -> None:
        self.configure(fg_color=MC_PANEL_LOW)
        self.grid_columnconfigure(0, weight=0)
        self.grid_columnconfigure(1, weight=1)
        self.grid_columnconfigure(2, weight=0)
        self.grid_rowconfigure(1, weight=1)

        # —— 顶栏：标题 + 模式切换 + 状态 ——
        top = ctk.CTkFrame(self, fg_color=MC_PANEL_LOW, corner_radius=0)
        top.grid(row=0, column=0, columnspan=3, sticky="ew", padx=10, pady=(8, 2))
        top.grid_columnconfigure(2, weight=1)

        ctk.CTkLabel(top, text="MC 建筑工作台", font=_font(17, True), text_color=MC_TEXT).grid(
            row=0, column=0, sticky="w", padx=(4, 16)
        )

        self.mode_var = ctk.StringVar(value=MODE_BROWSE)
        self.mode_seg = ctk.CTkSegmentedButton(
            top,
            values=[MODE_BROWSE, MODE_GENERATE, MODE_DESIGN, MODE_EDIT, MODE_TOOLS],
            variable=self.mode_var,
            command=self._on_mode_change,
            width=460,
            height=34,
            font=_font(13, True),
        )
        self.mode_seg.grid(row=0, column=1, sticky="w")

        self.status_var = ctk.StringVar(value="就绪")
        ctk.CTkLabel(
            top,
            textvariable=self.status_var,
            wraplength=460,
            justify="right",
            anchor="e",
            font=_font(11),
            text_color=MC_MUTED,
        ).grid(row=0, column=2, sticky="e", padx=(12, 4))

        # —— 左栏：建筑库（缩略图卡片列表，所有模式常驻）——
        self.left = ctk.CTkFrame(self, width=286, fg_color=MC_PANEL, corner_radius=10)
        self.left.grid(row=1, column=0, sticky="nsew", padx=(10, 4), pady=(4, 10))
        self.left.grid_propagate(False)
        self.left.grid_columnconfigure(0, weight=1)
        self._build_library_panel(self.left)

        # —— 右栏：情境面板（按模式切换内容）——
        self.right = ctk.CTkFrame(self, width=352, fg_color=MC_PANEL, corner_radius=10)
        self.right.grid(row=1, column=2, sticky="nsew", padx=(4, 10), pady=(4, 10))
        self.right.grid_propagate(False)
        self.right.grid_columnconfigure(0, weight=1)
        self.right.grid_rowconfigure(2, weight=1)

        head = ctk.CTkFrame(self.right, fg_color="transparent")
        head.grid(row=0, column=0, sticky="ew", padx=14, pady=(12, 0))
        self.inspector_title = ctk.CTkLabel(
            head, text="样本信息", font=_font(15, True), anchor="w", text_color=MC_TEXT
        )
        self.inspector_title.pack(side="left")

        self.mode_hint = ctk.CTkLabel(
            self.right,
            text="",
            wraplength=320,
            justify="left",
            anchor="w",
            font=_font(11),
            text_color=MC_MUTED,
        )
        self.mode_hint.grid(row=1, column=0, sticky="ew", padx=14, pady=(2, 6))

        self.inspector_body = ctk.CTkFrame(self.right, fg_color="transparent")
        self.inspector_body.grid(row=2, column=0, sticky="nsew", padx=(6, 2), pady=(0, 8))
        self.inspector_body.grid_rowconfigure(0, weight=1)
        self.inspector_body.grid_columnconfigure(0, weight=1)

        self.browse_frame = ctk.CTkScrollableFrame(self.inspector_body, fg_color="transparent")
        self.generate_frame = ctk.CTkScrollableFrame(self.inspector_body, fg_color="transparent")
        self.design_frame = ctk.CTkScrollableFrame(self.inspector_body, fg_color="transparent")
        self.edit_frame = ctk.CTkScrollableFrame(self.inspector_body, fg_color="transparent")
        self.tools_frame = ctk.CTkScrollableFrame(self.inspector_body, fg_color="transparent")

        self._build_browse_panel(self.browse_frame)
        self._build_generate_panel(self.generate_frame)
        self._build_design_panel(self.design_frame)
        self._build_edit_inspector(self.edit_frame)
        self._build_tools_panel(self.tools_frame)

        # —— 中栏：3D 画布 + 建造步骤 + 快捷栏 ——
        mid = ctk.CTkFrame(self, fg_color=MC_PANEL, corner_radius=10)
        mid.grid(row=1, column=1, sticky="nsew", padx=4, pady=(4, 10))
        mid.grid_rowconfigure(0, weight=1)
        mid.grid_columnconfigure(0, weight=1)

        canvas_host = ctk.CTkFrame(mid, fg_color=MC_PANEL_LOW, corner_radius=8)
        canvas_host.grid(row=0, column=0, sticky="nsew", padx=8, pady=(8, 2))
        canvas_host.grid_rowconfigure(0, weight=1)
        canvas_host.grid_columnconfigure(0, weight=1)

        self.fig = Figure(figsize=(7, 5.2), dpi=100)
        self.ax = self.fig.add_subplot(111, projection="3d")
        self.ax.set_title("3D 体素预览")
        self._draw_empty()

        self.canvas = FigureCanvasTkAgg(self.fig, master=canvas_host)
        self.canvas.draw()
        self.canvas.get_tk_widget().grid(row=0, column=0, sticky="nsew")
        self._bind_canvas_interactions()
        self._redraw_crosshair()

        self._build_steps_bar(mid)  # row 1
        self._build_hotbar(mid)  # row 2

        toolbar_frame = tk.Frame(mid, bg=MC_PANEL)
        toolbar_frame.grid(row=3, column=0, sticky="ew", padx=8, pady=(0, 4))
        self.toolbar = NavigationToolbar2Tk(self.canvas, toolbar_frame)
        self.toolbar.update()

    # ------------------------------------------------------------------
    # 左栏：建筑库（缩略图卡片）
    # ------------------------------------------------------------------
    def _build_library_panel(self, parent: ctk.CTkFrame) -> None:
        parent.grid_columnconfigure(0, weight=1)
        parent.grid_rowconfigure(5, weight=1)

        head = ctk.CTkFrame(parent, fg_color="transparent")
        head.grid(row=0, column=0, sticky="ew", padx=12, pady=(12, 4))
        ctk.CTkLabel(head, text="建筑库", font=_font(15, True), text_color=MC_TEXT).pack(side="left")
        self.lib_count_label = ctk.CTkLabel(head, text="", font=_font(11), text_color=MC_MUTED)
        self.lib_count_label.pack(side="right")

        self.sample_var = ctk.StringVar(value="")
        self.batch_var = ctk.StringVar(value="默认 samples")
        self.batch_menu = ctk.CTkOptionMenu(
            parent,
            variable=self.batch_var,
            values=["默认 samples"],
            command=self.on_batch_selected,
            height=28,
            font=_font(11),
            fg_color=MC_SLOT,
            button_color=MC_BORDER,
            button_hover_color=MC_CARD_HOVER,
            dropdown_font=_font(11),
        )
        self.batch_menu.grid(row=1, column=0, sticky="ew", padx=12, pady=(0, 4))

        dir_row = ctk.CTkFrame(parent, fg_color="transparent")
        dir_row.grid(row=2, column=0, sticky="ew", padx=10, pady=(0, 2))
        for text, width, cmd in (
            ("选目录…", 84, self.pick_sample_dir),
            ("刷新", 62, self.refresh_lists),
            ("打开", 56, self.open_out_dir),
        ):
            ctk.CTkButton(
                dir_row,
                text=text,
                width=width,
                height=26,
                font=_font(11),
                fg_color=MC_SLOT,
                hover_color=MC_CARD_HOVER,
                border_width=1,
                border_color=MC_BORDER,
                command=cmd,
            ).pack(side="left", padx=(2, 4))

        self.out_dir_label = ctk.CTkLabel(
            parent, text="", font=_font(10), text_color=MC_MUTED, anchor="w"
        )
        self.out_dir_label.grid(row=3, column=0, sticky="ew", padx=12, pady=(2, 4))

        ctk.CTkLabel(
            parent, text="样本（点卡片预览）", font=_font(11, True), text_color=MC_MUTED, anchor="w"
        ).grid(row=4, column=0, sticky="ew", padx=12, pady=(2, 2))

        self.library_list = ctk.CTkScrollableFrame(
            parent,
            fg_color=MC_PANEL_LOW,
            corner_radius=8,
            scrollbar_button_color=MC_BORDER,
            scrollbar_button_hover_color=MC_ACCENT,
        )
        self.library_list.grid(row=5, column=0, sticky="nsew", padx=(8, 4), pady=(0, 8))

        ctk.CTkLabel(
            parent,
            text="滚轮浏览 · 点卡片换样本 · 顶部下拉切批次",
            font=_font(10),
            text_color=MC_MUTED,
            anchor="w",
        ).grid(row=6, column=0, sticky="ew", padx=12, pady=(0, 10))

    def _refresh_sample_cards(self) -> None:
        if not hasattr(self, "library_list"):
            return
        for w in self.library_list.winfo_children():
            w.destroy()
        self._sample_cards.clear()
        self._card_images.clear()
        self._thumb_queue.clear()

        samples = list_sample_files(self.out_dir)
        if hasattr(self, "lib_count_label"):
            self.lib_count_label.configure(text=f"{len(samples)} 个")
        if not samples:
            ctk.CTkLabel(
                self.library_list, text="此目录没有 sample_*.npz", font=_font(11), text_color=MC_MUTED
            ).pack(pady=16)
            return

        for p in samples:
            card = ctk.CTkFrame(
                self.library_list, fg_color=MC_CARD, corner_radius=8, border_width=2,
                border_color=MC_CARD,
            )
            card.pack(fill="x", padx=(4, 8), pady=3)
            card.grid_columnconfigure(1, weight=1)

            thumb = ctk.CTkLabel(
                card, text="", width=THUMB_W, height=THUMB_H,
                fg_color=MC_PANEL_LOW, corner_radius=6,
            )
            thumb.grid(row=0, column=0, rowspan=2, padx=6, pady=6, sticky="nw")
            thumb.grid_propagate(False)

            name_l = ctk.CTkLabel(
                card, text=p.stem[:24], font=_font(11, True), text_color=MC_TEXT,
                anchor="w", justify="left", wraplength=118,
            )
            name_l.grid(row=0, column=1, sticky="w", padx=(0, 6), pady=(8, 0))
            meta_l = ctk.CTkLabel(
                card, text="…", font=_font(10), text_color=MC_MUTED, anchor="w"
            )
            meta_l.grid(row=1, column=1, sticky="w", padx=(0, 6), pady=(0, 6))

            for w in (card, thumb, name_l, meta_l):
                w.bind("<Button-1>", lambda _e, path=p: self._on_library_click(path))

            self._sample_cards[p] = (card, thumb, name_l, meta_l)
            self._thumb_queue.append(p)

        self._mark_sample_card(self.current_path)
        self.after(40, self._pump_thumbs)

    def _pump_thumbs(self) -> None:
        if not self._thumb_queue:
            return
        path = self._thumb_queue.pop(0)
        item = self._sample_cards.get(path)
        if item is None:
            self.after(20, self._pump_thumbs)
            return
        _card, thumb, _name_l, meta_l = item
        try:
            non_air, nbytes = sample_stats(path)
            meta_l.configure(text=f"{non_air:,} 块 · {nbytes / 1024:.0f} KB")
        except Exception:
            pass
        try:
            png = render_thumb(path, self.palette, size=(THUMB_W * 2, THUMB_H * 2))
            if png is not None:
                from PIL import Image

                img = Image.open(png).convert("RGBA")
                icon = ctk.CTkImage(light_image=img, dark_image=img, size=(THUMB_W, THUMB_H))
                self._card_images.append(icon)
                thumb.configure(image=icon, text="")
            else:
                thumb.configure(text="无预览", font=_font(10), text_color=MC_MUTED)
        except Exception:
            thumb.configure(text="无预览", font=_font(10), text_color=MC_MUTED)
        if self._thumb_queue:
            self.after(30, self._pump_thumbs)

    def _on_library_click(self, path: Path) -> None:
        self.on_sample_selected(Path(path).name)

    def _mark_sample_card(self, path: Path | None) -> None:
        name = Path(path).name if path is not None else None
        for p, (card, _t, _n, _m) in getattr(self, "_sample_cards", {}).items():
            active = name is not None and p.name == name
            try:
                card.configure(
                    fg_color=MC_CARD_ACTIVE if active else MC_CARD,
                    border_color=MC_ACCENT if active else MC_CARD,
                )
            except Exception:
                pass

    # ------------------------------------------------------------------
    # 中栏：建造步骤条
    # ------------------------------------------------------------------
    def _build_steps_bar(self, parent: ctk.CTkFrame) -> None:
        wrap = ctk.CTkFrame(parent, fg_color=MC_PANEL_LOW, corner_radius=8)
        wrap.grid(row=1, column=0, sticky="ew", padx=8, pady=2)
        wrap.grid_columnconfigure(0, weight=1)

        head = ctk.CTkFrame(wrap, fg_color="transparent")
        head.grid(row=0, column=0, sticky="ew", padx=8, pady=(6, 0))
        ctk.CTkLabel(head, text="建造步骤", font=_font(12, True), text_color=MC_TEXT).pack(side="left")
        self.steps_hint_label = ctk.CTkLabel(head, text="未加载样本", font=_font(10), text_color=MC_MUTED)
        self.steps_hint_label.pack(side="left", padx=(10, 0))

        self.steps_play_btn = ctk.CTkButton(
            head,
            text="▶ 播放",
            width=68,
            height=24,
            font=_font(11, True),
            fg_color=MC_ACCENT,
            hover_color=MC_ACCENT_HOVER,
            text_color="#14210f",
            command=self._toggle_steps_play,
        )
        self.steps_play_btn.pack(side="right")
        self.steps_full_btn = ctk.CTkButton(
            head,
            text="完整",
            width=56,
            height=24,
            font=_font(11),
            fg_color=MC_SLOT,
            hover_color=MC_CARD_HOVER,
            text_color=MC_TEXT,
            border_width=1,
            border_color=MC_BORDER,
            command=self._show_full_building,
        )
        self.steps_full_btn.pack(side="right", padx=(0, 4))

        chips = ctk.CTkFrame(wrap, fg_color="transparent")
        chips.grid(row=1, column=0, sticky="ew", padx=8, pady=(4, 2))
        self._step_chips = []
        for key in STAGE_ORDER:
            chip = ctk.CTkButton(
                chips,
                text=f"· {STAGE_LABELS[key]}",
                height=26,
                font=_font(11),
                fg_color=MC_SLOT,
                hover_color=MC_CARD_HOVER,
                text_color=MC_MUTED,
                border_width=1,
                border_color=MC_BORDER,
                command=lambda k=key: self._on_step_click(k),
            )
            chip.pack(side="left", fill="x", expand=True, padx=(0, 4))
            self._step_chips.append((key, chip))

        self.steps_progress = ctk.CTkProgressBar(wrap, height=4, progress_color=MC_ACCENT)
        self.steps_progress.set(0)
        self.steps_progress.grid(row=2, column=0, sticky="ew", padx=8, pady=(0, 6))

    def _refresh_steps(self) -> None:
        self._cancel_steps_play()
        self._steps = []
        self._step_by_key = {}
        self._step_index = None
        if self.current_voxels is not None:
            try:
                self._steps = compute_stages(self.current_voxels, palette=self.palette)
            except Exception:
                self._steps = []
            self._step_by_key = {s["key"]: i for i, s in enumerate(self._steps)}
        self._update_steps_bar()

    def _update_steps_bar(self) -> None:
        if not getattr(self, "_step_chips", None):
            return
        active_key = None
        if self._step_index is not None and 0 <= self._step_index < len(self._steps):
            active_key = self._steps[self._step_index]["key"]

        for key, chip in self._step_chips:
            idx = self._step_by_key.get(key)
            has = idx is not None
            is_active = key == active_key
            text = f"{idx + 1}. {STAGE_LABELS[key]}" if has else f"· {STAGE_LABELS[key]}"
            try:
                chip.configure(
                    text=text,
                    state="normal" if has else "disabled",
                    fg_color=MC_ACCENT if is_active else (MC_CARD_HOVER if has else MC_SLOT),
                    hover_color=MC_ACCENT_HOVER if is_active else MC_CARD_HOVER,
                    text_color="#14210f" if is_active else (MC_TEXT if has else MC_MUTED),
                    border_color=MC_ACCENT if is_active else MC_BORDER,
                )
            except Exception:
                pass

        if not hasattr(self, "steps_hint_label"):
            return
        if not self._steps:
            self.steps_hint_label.configure(text="未加载样本")
            self.steps_progress.set(0)
            return

        text = f"{len(self._steps)} 阶段 · 共 {self._steps[-1]['total']} 块"
        if active_key is not None:
            step = self._steps[self._step_index]
            pct = step["count"] / max(1, step["total"]) * 100.0
            text += f" · 当前 {step['label']}（本阶段 {pct:.0f}%，累计 {step['percent']:.0f}%）"
            self.steps_progress.set((self._step_index + 1) / len(self._steps))
        else:
            self.steps_progress.set(0)
        self.steps_hint_label.configure(text=text)

    def _on_step_click(self, key: str) -> None:
        idx = self._step_by_key.get(key)
        if idx is None:
            return
        self._cancel_steps_play()
        self._render_step_view(idx)

    def _render_step_view(self, index: int | None) -> None:
        if self.current_voxels is None:
            return
        if index is None or index < 0 or index >= len(self._steps):
            self._step_index = None
            self._update_steps_bar()
            self.render_voxels(self.current_voxels)
            return
        self._step_index = int(index)
        self._update_steps_bar()
        self.render_voxels(apply_upto(self.current_voxels, self._steps, self._step_index))
        step = self._steps[self._step_index]
        self._set_status(
            f"步骤 {self._step_index + 1}/{len(self._steps)}：{step['label']} — {step['hint']}"
        )

    def _show_full_building(self) -> None:
        self._cancel_steps_play()
        self._render_step_view(None)

    def _toggle_steps_play(self) -> None:
        if self._steps_play_job is not None:
            self._cancel_steps_play()
            return
        if not self._steps or self.current_voxels is None:
            self._set_status("没有可播放的建造步骤")
            return
        self._step_index = -1
        if hasattr(self, "steps_play_btn"):
            self.steps_play_btn.configure(text="■ 停止")
        self._advance_step()

    def _advance_step(self) -> None:
        self._steps_play_job = None
        if not self._steps:
            self._finish_play()
            return
        nxt = 0 if self._step_index is None else self._step_index + 1
        if nxt >= len(self._steps):
            self._finish_play()
            return
        self._render_step_view(nxt)
        self._steps_play_job = self.after(900, self._advance_step)

    def _finish_play(self) -> None:
        self._steps_play_job = None
        if hasattr(self, "steps_play_btn"):
            try:
                self.steps_play_btn.configure(text="▶ 播放")
            except Exception:
                pass
        self._step_index = None
        self._update_steps_bar()
        if self.current_voxels is not None:
            self.render_voxels(self.current_voxels)
        self._set_status("建造步骤播放完成（已回到完整建筑）")

    def _cancel_steps_play(self) -> None:
        if getattr(self, "_steps_play_job", None) is not None:
            try:
                self.after_cancel(self._steps_play_job)
            except Exception:
                pass
            self._steps_play_job = None
        if hasattr(self, "steps_play_btn"):
            try:
                self.steps_play_btn.configure(text="▶ 播放")
            except Exception:
                pass

    # ------------------------------------------------------------------
    # 右栏：编辑模式（材质库 + 建模控件）
    # ------------------------------------------------------------------
    def _build_edit_inspector(self, parent: ctk.CTkFrame) -> None:
        parent.grid_columnconfigure(0, weight=1)
        self._build_edit_panel(parent)  # 占用 row 0-3

        head = ctk.CTkFrame(parent, fg_color="transparent")
        head.grid(row=5, column=0, sticky="ew", padx=10, pady=(10, 2))
        ctk.CTkLabel(head, text="材质库", font=_font(13, True), text_color=MC_TEXT).pack(side="left")
        ctk.CTkButton(
            head,
            text="搜索",
            width=64,
            height=24,
            font=_font(11),
            fg_color=MC_SLOT,
            hover_color=MC_CARD_HOVER,
            border_width=1,
            border_color=MC_BORDER,
            command=self._jump_to_material_picker,
        ).pack(side="right")

        self.mat_filter = ctk.CTkEntry(
            parent, placeholder_text="过滤材质，如 stone / 橡木", height=28, font=_font(11)
        )
        self.mat_filter.grid(row=6, column=0, sticky="ew", padx=10, pady=(2, 2))
        self.mat_filter.bind("<KeyRelease>", lambda _e: self._refresh_material_grid())

        self.material_grid = ctk.CTkFrame(parent, fg_color="transparent")
        self.material_grid.grid(row=7, column=0, sticky="ew", padx=8, pady=(2, 8))

        ctk.CTkLabel(
            parent,
            text="点材质 = 写入当前快捷栏格 + 设为放置/涂改目标",
            font=_font(10),
            text_color=MC_MUTED,
            anchor="w",
            wraplength=300,
            justify="left",
        ).grid(row=8, column=0, sticky="w", padx=10, pady=(0, 6))

        self._edit_controls = ctk.CTkFrame(parent, fg_color="transparent")
        self._edit_controls.grid(row=9, column=0, sticky="ew", padx=0, pady=(4, 10))
        self._build_right_edit(self._edit_controls)

        self._mat_grid_built = False  # 首次进入编辑页再构建，省启动时间

    def _material_candidates(self, query: str = "") -> list[str]:
        q = (query or "").strip().lower()
        names = list(COMMON_MATERIALS)
        if q:
            names = [
                n
                for n in names
                if q in n.lower() or q in str(block_zh_name(n) or "").lower()
            ]
            for bid in sorted(self.palette):
                name = self.palette[bid]
                if name in names:
                    continue
                if q in name.lower() or q in str(block_zh_name(name) or "").lower():
                    names.append(name)
        return names[:48]

    def _refresh_material_grid(self) -> None:
        if not hasattr(self, "material_grid"):
            return
        self._mat_grid_built = True
        for w in self.material_grid.winfo_children():
            w.destroy()
        self._mat_icons = []

        query = ""
        if hasattr(self, "mat_filter"):
            try:
                query = self.mat_filter.get()
            except Exception:
                query = ""
        names = self._material_candidates(query)
        if not names:
            ctk.CTkLabel(
                self.material_grid, text="无匹配材质", font=_font(11), text_color=MC_MUTED
            ).grid(row=0, column=0, padx=6, pady=8)
            return

        cols = 4
        for i, name in enumerate(names):
            label = block_zh_name(name) or short_block_name(name)
            btn = ctk.CTkButton(
                self.material_grid,
                text=label[:5],
                width=74,
                height=48,
                font=_font(9),
                fg_color=MC_SLOT,
                hover_color=MC_CARD_HOVER,
                text_color=MC_TEXT,
                border_width=1,
                border_color=MC_BORDER,
                compound="top",
                command=lambda n=name: self._pick_material(n),
            )
            try:
                pil = load_pil_icon(name, size=22)
                if pil is not None and hasattr(ctk, "CTkImage"):
                    icon = ctk.CTkImage(light_image=pil, dark_image=pil, size=(22, 22))
                    self._mat_icons.append(icon)
                    btn.configure(image=icon)
            except Exception:
                pass
            btn.grid(row=i // cols, column=i % cols, padx=2, pady=2, sticky="ew")
        for c in range(cols):
            self.material_grid.grid_columnconfigure(c, weight=1)

    def _pick_material(self, name: str) -> None:
        if name not in self.name_to_id:
            self._set_status(f"调色板中无此方块：{name}")
            return
        self._hotbar_names[self._hotbar_slot] = name
        self._set_target(name)
        self._refresh_hotbar_ui()
        self._flash_toast(
            f"快捷栏 {self._hotbar_slot + 1} → {block_zh_name(name) or short_block_name(name)}"
        )

    def _jump_to_material_picker(self) -> None:
        if self._mode != MODE_EDIT:
            self._switch_mode(MODE_EDIT)
        if not hasattr(self, "mat_filter"):
            return
        try:
            self.mat_filter.focus_set()
            self.edit_frame._parent_canvas.yview_moveto(0.25)
        except Exception:
            pass
        self._set_status("材质库：输入关键词过滤，点方块写入快捷栏")

    def _build_browse_panel(self, parent: ctk.CTkFrame) -> None:
        parent.grid_columnconfigure(0, weight=1)

        # —— 样本信息 + 视口控制（浏览模式的右栏）——
        self.info_box = ctk.CTkTextbox(
            parent,
            height=210,
            font=_font(12),
            fg_color=MC_PANEL_LOW,
            border_width=0,
            corner_radius=8,
            wrap="word",
        )
        self.info_box.grid(row=0, column=0, sticky="nsew", padx=6, pady=(0, 8))
        self.info_box.insert("1.0", "未加载样本")
        self.info_box.configure(state="disabled")

        ctk.CTkLabel(parent, text="视口", font=_font(12, True), text_color=MC_TEXT).grid(
            row=1, column=0, sticky="w", padx=6, pady=(4, 2)
        )
        self.style_switch = ctk.CTkSwitch(
            parent,
            text="性能模式（轨道 LOD，更快）",
            variable=self.style_perf_var,
            command=self._on_style_toggle,
            font=_font(11),
        )
        self.style_switch.grid(row=2, column=0, sticky="w", padx=6, pady=(4, 4))

        self.y_slice_label = ctk.CTkLabel(
            parent, text="Y 切片（拖低看室内；32 = 全高）", font=_font(11), text_color=MC_MUTED
        )
        self.y_slice_label.grid(row=3, column=0, sticky="w", padx=6, pady=(6, 0))
        self.y_slice_slider = ctk.CTkSlider(
            parent,
            from_=0,
            to=32,
            number_of_steps=32,
            variable=self.y_slice_var,
            command=lambda _v: self._on_y_slice(),
        )
        self.y_slice_slider.grid(row=4, column=0, sticky="ew", padx=6, pady=(0, 6))

        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.grid(row=5, column=0, sticky="ew", padx=6, pady=(4, 2))
        ctk.CTkButton(row, text="刷新列表", width=96, height=28, command=self.refresh_lists).pack(
            side="left"
        )
        ctk.CTkButton(
            row, text="打开文件夹", width=100, height=28, command=self.open_out_dir
        ).pack(side="left", padx=(6, 0))


        # ---- UX P2: schemes project list (browse) ----
        ctk.CTkLabel(parent, text="方案（项目）", font=ctk.CTkFont(weight="bold")).grid(
            row=11, column=0, sticky="w", padx=4, pady=(10, 2)
        )
        self.scheme_list_frame = ctk.CTkScrollableFrame(parent, height=120)
        self.scheme_list_frame.grid(row=12, column=0, sticky="nsew", padx=4, pady=2)
        parent.grid_rowconfigure(12, weight=1)

        sch_btns = ctk.CTkFrame(parent, fg_color="transparent")
        sch_btns.grid(row=13, column=0, sticky="ew", padx=4, pady=(4, 2))
        ctk.CTkButton(sch_btns, text="新建", width=60, height=28, command=self.on_scheme_new).pack(
            side="left", padx=1
        )
        ctk.CTkButton(sch_btns, text="打开", width=60, height=28, command=self.on_scheme_open).pack(
            side="left", padx=1
        )
        ctk.CTkButton(sch_btns, text="另存", width=60, height=28, command=self.on_scheme_save_as).pack(
            side="left", padx=1
        )
        ctk.CTkButton(sch_btns, text="保存", width=60, height=28, command=self.on_scheme_save).pack(
            side="left", padx=1
        )

        sch_btns2 = ctk.CTkFrame(parent, fg_color="transparent")
        sch_btns2.grid(row=14, column=0, sticky="ew", padx=4, pady=(2, 2))
        ctk.CTkButton(
            sch_btns2, text="导入投影", width=90, height=28, command=self.on_scheme_import_litematic
        ).pack(side="left", padx=1)
        ctk.CTkButton(
            sch_btns2, text="导入npz", width=90, height=28, command=self.on_scheme_import_npz
        ).pack(side="left", padx=1)
        ctk.CTkButton(
            sch_btns2, text="刷新", width=60, height=28, command=self._refresh_scheme_list
        ).pack(side="right", padx=1)

        self.open_folder_var = ctk.BooleanVar(value=True)
        ctk.CTkCheckBox(
            parent,
            text="导出后打开文件夹",
            variable=self.open_folder_var,
            width=180,
        ).grid(row=15, column=0, sticky="w", padx=4, pady=(4, 2))

        self.export_game_btn = ctk.CTkButton(
            parent,
            text="进游戏（导出 PCL）",
            command=self.on_export_to_game,
            height=36,
            font=ctk.CTkFont(size=14, weight="bold"),
            fg_color=("#1b7f4a", "#1b7f4a"),
            hover_color=("#146038", "#146038"),
        )
        self.export_game_btn.grid(row=16, column=0, sticky="ew", padx=4, pady=(4, 10))
        # UX_P2_SCHEMES

        # ---- UX P3: light in-game bridge ----
        ctk.CTkLabel(parent, text="游戏桥接（投影目录）", font=ctk.CTkFont(weight="bold")).grid(
            row=17, column=0, sticky="w", padx=4, pady=(8, 2)
        )
        self.bridge_status_label = ctk.CTkLabel(
            parent,
            text="检测中…",
            anchor="w",
            wraplength=280,
            text_color=("gray30", "gray70"),
            font=ctk.CTkFont(size=11),
        )
        self.bridge_status_label.grid(row=18, column=0, sticky="ew", padx=4, pady=(0, 2))

        self.bridge_list_frame = ctk.CTkScrollableFrame(parent, height=110)
        self.bridge_list_frame.grid(row=19, column=0, sticky="nsew", padx=4, pady=2)

        br_btns = ctk.CTkFrame(parent, fg_color="transparent")
        br_btns.grid(row=20, column=0, sticky="ew", padx=4, pady=(2, 2))
        ctk.CTkButton(
            br_btns, text="刷新投影", width=80, height=28, command=self._refresh_game_bridge
        ).pack(side="left", padx=1)
        ctk.CTkButton(
            br_btns, text="打开目录", width=80, height=28, command=self.on_open_schematics_folder
        ).pack(side="left", padx=1)
        ctk.CTkButton(
            br_btns, text="定位文件", width=80, height=28, command=self.on_reveal_selected_litematic
        ).pack(side="left", padx=1)

        br_btns2 = ctk.CTkFrame(parent, fg_color="transparent")
        br_btns2.grid(row=21, column=0, sticky="ew", padx=4, pady=(2, 2))
        ctk.CTkButton(
            br_btns2, text="复制文件名", width=90, height=28, command=self.on_copy_export_name
        ).pack(side="left", padx=1)
        ctk.CTkButton(
            br_btns2, text="建造步骤", width=90, height=28, command=self.on_show_build_steps
        ).pack(side="left", padx=1)
        self.bridge_auto_var = ctk.BooleanVar(value=True)
        ctk.CTkCheckBox(
            br_btns2,
            text="自动刷新",
            variable=self.bridge_auto_var,
            width=90,
            command=self._on_bridge_auto_toggle,
        ).pack(side="right", padx=1)

        self.bridge_hint_label = ctk.CTkLabel(
            parent,
            text="高亮=本应用导出（夜齐_/夜坡_/ai_…）。非游戏内 HUD。",
            anchor="w",
            wraplength=280,
            text_color=("gray40", "gray65"),
            font=ctk.CTkFont(size=10),
        )
        self.bridge_hint_label.grid(row=22, column=0, sticky="ew", padx=4, pady=(2, 8))
        # UX_P3_BRIDGE


    def _build_generate_panel(self, parent: ctk.CTkFrame) -> None:
        parent.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(parent, text="Checkpoint", font=ctk.CTkFont(weight="bold")).grid(
            row=0, column=0, sticky="w", padx=4, pady=(4, 2)
        )
        self.ckpt_var = ctk.StringVar(value="last.pt")
        self.ckpt_menu = ctk.CTkOptionMenu(parent, variable=self.ckpt_var, values=["last.pt"])
        self.ckpt_menu.grid(row=1, column=0, sticky="ew", padx=4, pady=2)

        ctk.CTkLabel(parent, text="风格").grid(row=2, column=0, sticky="w", padx=4, pady=(12, 2))
        self.style_var = ctk.StringVar(value="medieval")
        self.style_menu = ctk.CTkOptionMenu(parent, variable=self.style_var, values=["medieval"])
        self.style_menu.grid(row=3, column=0, sticky="ew", padx=4, pady=2)

        ctk.CTkLabel(parent, text="地形").grid(row=4, column=0, sticky="w", padx=4, pady=(12, 2))
        self.terrain_var = ctk.StringVar(value="flat")
        self.terrain_menu = ctk.CTkOptionMenu(parent, variable=self.terrain_var, values=["flat"])
        self.terrain_menu.grid(row=5, column=0, sticky="ew", padx=4, pady=2)

        ctk.CTkLabel(parent, text="数量 (1–8)").grid(row=6, column=0, sticky="w", padx=4, pady=(12, 2))
        self.num_var = ctk.IntVar(value=1)
        self.num_slider = ctk.CTkSlider(
            parent, from_=1, to=8, number_of_steps=7, variable=self.num_var, command=self._on_num
        )
        self.num_slider.grid(row=7, column=0, sticky="ew", padx=4, pady=2)
        self.num_label = ctk.CTkLabel(parent, text="1")
        self.num_label.grid(row=8, column=0, sticky="w", padx=4)

        ctk.CTkLabel(parent, text="随机度 Temperature").grid(
            row=9, column=0, sticky="w", padx=4, pady=(12, 2)
        )
        self.temp_var = ctk.DoubleVar(value=1.0)
        self.temp_slider = ctk.CTkSlider(
            parent, from_=0.3, to=2.0, number_of_steps=34, variable=self.temp_var, command=self._on_temp
        )
        self.temp_slider.grid(row=10, column=0, sticky="ew", padx=4, pady=2)
        self.temp_label = ctk.CTkLabel(parent, text="1.00")
        self.temp_label.grid(row=11, column=0, sticky="w", padx=4)

        self.struct_var = ctk.BooleanVar(value=True)
        self.struct_chk = ctk.CTkCheckBox(
            parent,
            text="结构约束（空心壳/楼板/屋顶修补）",
            variable=self.struct_var,
        )
        self.struct_chk.grid(row=12, column=0, sticky="w", padx=4, pady=(14, 2))

        ctk.CTkLabel(parent, text="约束模式").grid(row=13, column=0, sticky="w", padx=4, pady=(8, 2))
        self.struct_mode_var = ctk.StringVar(value="repair")
        self.struct_mode_menu = ctk.CTkOptionMenu(
            parent,
            variable=self.struct_mode_var,
            values=["repair", "reject", "reject_then_repair"],
        )
        self.struct_mode_menu.grid(row=14, column=0, sticky="ew", padx=4, pady=2)

        self.gen_btn = ctk.CTkButton(
            parent,
            text="生成建筑",
            command=self.on_generate,
            height=40,
            font=ctk.CTkFont(size=15, weight="bold"),
        )
        self.gen_btn.grid(row=15, column=0, sticky="ew", padx=4, pady=(16, 8))

        ctk.CTkLabel(
            parent,
            text="生成成功后会自动切到「浏览」并打开新样本。结构约束为 Phase2，不重训。",
            wraplength=260,
            justify="left",
            text_color=("gray40", "gray70"),
            font=ctk.CTkFont(size=12),
        ).grid(row=16, column=0, sticky="w", padx=4, pady=(4, 8))

        ctk.CTkLabel(parent, text="文字速建（AI）", font=ctk.CTkFont(weight="bold")).grid(
            row=17, column=0, sticky="w", padx=4, pady=(14, 2)
        )
        self.quick_text_var = ctk.StringVar()
        self.quick_text = ctk.CTkEntry(
            parent,
            placeholder_text="一句话：带塔楼的中世纪石堡",
            textvariable=self.quick_text_var,
        )
        self.quick_text.grid(row=18, column=0, sticky="ew", padx=4, pady=2)
        self.quick_text.bind("<Return>", lambda _e: self.on_quick_build())
        self.quick_build_btn = ctk.CTkButton(
            parent,
            text="速建",
            command=self.on_quick_build,
            height=32,
            fg_color=("#6c3483", "#6c3483"),
            hover_color=("#4a235a", "#4a235a"),
        )
        self.quick_build_btn.grid(row=19, column=0, sticky="ew", padx=4, pady=(4, 4))
        ctk.CTkLabel(
            parent,
            text="离线关键词启发式即可用；有 API Key 时理解更准。数量/随机度沿用上方滑条。",
            wraplength=260,
            justify="left",
            text_color=("gray40", "gray70"),
            font=ctk.CTkFont(size=12),
        ).grid(row=20, column=0, sticky="w", padx=4, pady=(0, 8))

        ctk.CTkLabel(parent, text="细节与修补", font=ctk.CTkFont(weight="bold")).grid(
            row=21, column=0, sticky="w", padx=4, pady=(12, 2)
        )
        self.look_harden_var = ctk.BooleanVar(value=True)
        ctk.CTkCheckBox(
            parent,
            text="细节增强（统一材质 / 补壳防漏）",
            variable=self.look_harden_var,
        ).grid(row=22, column=0, sticky="w", padx=4, pady=(2, 2))
        self.preserve_windows_var = ctk.BooleanVar(value=True)
        ctk.CTkCheckBox(
            parent, text="保留窗户开口", variable=self.preserve_windows_var
        ).grid(row=23, column=0, sticky="w", padx=4, pady=2)
        self.window_glass_var = ctk.BooleanVar(value=True)
        ctk.CTkCheckBox(
            parent, text="窗户补玻璃", variable=self.window_glass_var
        ).grid(row=24, column=0, sticky="w", padx=4, pady=2)

        ctk.CTkLabel(parent, text="结构重试次数").grid(row=25, column=0, sticky="w", padx=4, pady=(10, 2))
        self.struct_tries_var = ctk.IntVar(value=8)
        self.struct_tries_slider = ctk.CTkSlider(
            parent, from_=1, to=16, number_of_steps=15,
            variable=self.struct_tries_var, command=self._on_struct_tries,
        )
        self.struct_tries_slider.grid(row=26, column=0, sticky="ew", padx=4, pady=2)
        self.struct_tries_label = ctk.CTkLabel(parent, text="8")
        self.struct_tries_label.grid(row=27, column=0, sticky="w", padx=4)
        ctk.CTkLabel(
            parent,
            text="重试次数越大越容易凑出合格结构，但耗时更久。",
            wraplength=260,
            justify="left",
            text_color=("gray40", "gray70"),
            font=ctk.CTkFont(size=12),
        ).grid(row=28, column=0, sticky="w", padx=4, pady=(2, 8))

        ctk.CTkLabel(parent, text="批量速建（每行一条）", font=ctk.CTkFont(weight="bold")).grid(
            row=29, column=0, sticky="w", padx=4, pady=(12, 2)
        )
        self.batch_text = ctk.CTkTextbox(parent, height=76)
        self.batch_text.grid(row=30, column=0, sticky="ew", padx=4, pady=2)
        self.batch_text.insert(
            "1.0", "中世纪石堡\n现代白色混凝土别墅\n雪山旁的木屋"
        )
        self.batch_btn = ctk.CTkButton(
            parent,
            text="批量速建",
            command=self.on_batch_build,
            height=32,
            fg_color=("#1b6f8a", "#1b6f8a"),
            hover_color=("#14536a", "#14536a"),
        )
        self.batch_btn.grid(row=31, column=0, sticky="ew", padx=4, pady=(4, 4))
        ctk.CTkLabel(
            parent,
            text="最多 6 条，每条各出一座；结束后自动打开第一座，其余在左栏建筑库里。",
            wraplength=260,
            justify="left",
            text_color=("gray40", "gray70"),
            font=ctk.CTkFont(size=12),
        ).grid(row=32, column=0, sticky="w", padx=4, pady=(0, 8))

        ctk.CTkLabel(parent, text="多张候选择优", font=ctk.CTkFont(weight="bold")).grid(
            row=33, column=0, sticky="w", padx=4, pady=(12, 2)
        )
        self.rank_var = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(
            parent, text="生成多张，自动打开最高分", variable=self.rank_var
        ).grid(row=34, column=0, sticky="w", padx=4, pady=2)
        self.rank_num_var = ctk.IntVar(value=4)
        self.rank_num_label = ctk.CTkLabel(parent, text="候选数：4")
        self.rank_num_label.grid(row=35, column=0, sticky="w", padx=4, pady=(6, 0))
        ctk.CTkSlider(
            parent, from_=2, to=8, number_of_steps=6,
            variable=self.rank_num_var, command=self._on_rank_num,
        ).grid(row=36, column=0, sticky="ew", padx=4, pady=2)
        ctk.CTkLabel(
            parent,
            text="打分看填充率、左右对称、体量与连通性；未入选的样本仍留在建筑库里。",
            wraplength=260,
            justify="left",
            text_color=("gray40", "gray70"),
            font=ctk.CTkFont(size=12),
        ).grid(row=37, column=0, sticky="w", padx=4, pady=(2, 8))


    def _build_design_panel(self, parent: ctk.CTkFrame) -> None:
        parent.grid_columnconfigure(0, weight=1)
        parent.grid_rowconfigure(0, weight=1)
        scroll = ctk.CTkScrollableFrame(parent, fg_color="transparent")
        scroll.grid(row=0, column=0, sticky="nsew")
        scroll.grid_columnconfigure(0, weight=1)
        parent = scroll  # 后续控件铺在可滚动区内

        ctk.CTkLabel(parent, text="截图（可选）", font=ctk.CTkFont(weight="bold")).grid(
            row=0, column=0, sticky="w", padx=4, pady=(4, 2)
        )
        shot_row = ctk.CTkFrame(parent, fg_color="transparent")
        shot_row.grid(row=1, column=0, sticky="ew", padx=4, pady=2)
        shot_row.grid_columnconfigure(0, weight=1)
        self.design_image_var = ctk.StringVar(value="未选择截图")
        ctk.CTkLabel(shot_row, textvariable=self.design_image_var, wraplength=160, anchor="w").grid(
            row=0, column=0, sticky="ew"
        )
        ctk.CTkButton(shot_row, text="选择…", width=70, command=self.on_pick_design_image).grid(
            row=0, column=1, padx=(6, 0)
        )
        ctk.CTkButton(shot_row, text="清除", width=56, command=self.on_clear_design_image).grid(
            row=0, column=2, padx=(4, 0)
        )

        ctk.CTkLabel(parent, text="文字要求", font=ctk.CTkFont(weight="bold")).grid(
            row=2, column=0, sticky="w", padx=4, pady=(12, 2)
        )
        self.design_text = ctk.CTkTextbox(parent, height=90)
        self.design_text.grid(row=3, column=0, sticky="ew", padx=4, pady=2)
        self.design_text.insert("1.0", "例如：雪山旁的中世纪石堡，要有塔楼")

        ctk.CTkLabel(parent, text="推断结果（可手改）", font=ctk.CTkFont(weight="bold")).grid(
            row=4, column=0, sticky="w", padx=4, pady=(12, 2)
        )
        infer_box = ctk.CTkFrame(parent, fg_color="transparent")
        infer_box.grid(row=5, column=0, sticky="ew", padx=4, pady=2)
        infer_box.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(infer_box, text="风格").grid(row=0, column=0, sticky="w")
        self.design_style_var = ctk.StringVar(value="medieval")
        self.design_style_menu = ctk.CTkOptionMenu(
            infer_box, variable=self.design_style_var, values=["medieval"]
        )
        self.design_style_menu.grid(row=1, column=0, sticky="ew", pady=2)

        ctk.CTkLabel(infer_box, text="地形").grid(row=2, column=0, sticky="w", pady=(8, 0))
        self.design_terrain_var = ctk.StringVar(value="flat")
        self.design_terrain_menu = ctk.CTkOptionMenu(
            infer_box, variable=self.design_terrain_var, values=["flat"]
        )
        self.design_terrain_menu.grid(row=3, column=0, sticky="ew", pady=2)

        self.design_meta_var = ctk.StringVar(value="尚未理解。无 API Key 时用文字关键词 + 截图色调启发式。")
        ctk.CTkLabel(
            infer_box,
            textvariable=self.design_meta_var,
            wraplength=260,
            justify="left",
            anchor="w",
            text_color=("gray40", "gray70"),
            font=ctk.CTkFont(size=12),
        ).grid(row=4, column=0, sticky="ew", pady=(10, 4))

        self.design_spec_box = ctk.CTkTextbox(infer_box, height=110)
        self.design_spec_box.grid(row=5, column=0, sticky="nsew", pady=(4, 4))
        self.design_spec_box.insert("1.0", "点「理解要求」或「理解并生成」。")
        self.design_spec_box.configure(state="disabled")
        infer_box.grid_rowconfigure(5, weight=1)

        btn_row = ctk.CTkFrame(parent, fg_color="transparent")
        btn_row.grid(row=6, column=0, sticky="ew", padx=4, pady=(12, 4))
        self.design_understand_btn = ctk.CTkButton(
            btn_row, text="理解要求", width=110, command=self.on_design_understand
        )
        self.design_understand_btn.pack(side="left", padx=(0, 6))
        self.design_gen_btn = ctk.CTkButton(
            btn_row,
            text="理解并生成",
            width=130,
            command=self.on_design_generate,
            font=ctk.CTkFont(weight="bold"),
            height=36,
        )
        self.design_gen_btn.pack(side="left")

        api_hint = (
            "已检测到 OPENAI_API_KEY，理解时会走视觉 API。"
            if api_key_available()
            else "未检测到 OPENAI_API_KEY：文字关键词 + 截图色调启发式；请手改风格/地形。"
        )
        ctk.CTkLabel(
            parent,
            text=api_hint,
            wraplength=260,
            justify="left",
            text_color=("gray40", "gray70"),
            font=ctk.CTkFont(size=12),
        ).grid(row=7, column=0, sticky="w", padx=4, pady=(4, 8))

        ctk.CTkLabel(parent, text="图纸 / 草图识别", font=ctk.CTkFont(weight="bold")).grid(
            row=8, column=0, sticky="w", padx=4, pady=(16, 2)
        )
        bp_row = ctk.CTkFrame(parent, fg_color="transparent")
        bp_row.grid(row=9, column=0, sticky="ew", padx=4, pady=2)
        self.blueprint_btn = ctk.CTkButton(
            bp_row, text="导入图纸生成", width=130, command=self.on_import_blueprint
        )
        self.blueprint_btn.pack(side="left")
        ctk.CTkLabel(
            parent,
            text="支持手绘线稿或涂黑的平面图：自动识别轮廓，按上方所选风格拉起建筑壳（本地识别，不走 API）。",
            wraplength=260,
            justify="left",
            text_color=("gray40", "gray70"),
            font=ctk.CTkFont(size=12),
        ).grid(row=10, column=0, sticky="w", padx=4, pady=(4, 8))

    def _build_edit_panel(self, parent: ctk.CTkFrame) -> None:
        """左栏编辑提示；具体控件在右栏。"""
        parent.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            parent,
            text="右侧面板操作步骤：",
            font=ctk.CTkFont(weight="bold"),
        ).grid(row=0, column=0, sticky="w", padx=4, pady=(4, 6))
        steps = (
            "建模（接近 MCBlock）：\n"
            "· 选工具后在 3D 上点击\n"
            "· 破坏 / 放置 / 涂改 / 移动\n"
            "· 选中后可用微调按钮\n"
            "——\n"
            "批量：列表选源 → 目标 → 替换\n"
            "最后另存 / 导出 companion"
        )
        ctk.CTkLabel(parent, text=steps, justify="left", anchor="w").grid(
            row=1, column=0, sticky="nw", padx=4, pady=4
        )
        self.source_label_left = ctk.CTkLabel(
            parent, text="源方块：未选择", wraplength=260, justify="left", anchor="w"
        )
        self.source_label_left.grid(row=2, column=0, sticky="ew", padx=4, pady=(16, 4))

        ctk.CTkLabel(
            parent,
            text="有未保存修改时切换样本会提示。",
            wraplength=260,
            justify="left",
            text_color=("gray40", "gray70"),
            font=ctk.CTkFont(size=12),
        ).grid(row=3, column=0, sticky="w", padx=4, pady=(12, 8))

    def _build_right_edit(self, right: ctk.CTkFrame) -> None:
        ctk.CTkLabel(right, text="编辑 / 建模", font=ctk.CTkFont(size=16, weight="bold")).grid(
            row=0, column=0, sticky="w", padx=14, pady=(14, 2)
        )

        # —— MCBlock-like voxel tools ——
        ctk.CTkLabel(right, text="体素工具（点 3D）", font=ctk.CTkFont(weight="bold")).grid(
            row=1, column=0, sticky="w", padx=14, pady=(8, 2)
        )
        self.voxel_tool_var = ctk.StringVar(value="选择")
        self.voxel_tool_seg = ctk.CTkSegmentedButton(
            right,
            values=["选择", "破坏", "放置", "涂改", "移动"],
            variable=self.voxel_tool_var,
            command=self._on_voxel_tool_change,
            width=280,
            height=28,
            font=ctk.CTkFont(size=12),
        )
        self.voxel_tool_seg.grid(row=2, column=0, sticky="ew", padx=10, pady=2)
        self.sel_pos_label = ctk.CTkLabel(
            right, text="选中：无", anchor="w", wraplength=280, justify="left"
        )
        self.sel_pos_label.grid(row=3, column=0, sticky="ew", padx=14, pady=(2, 2))
        nudge_row = ctk.CTkFrame(right, fg_color="transparent")
        nudge_row.grid(row=4, column=0, sticky="ew", padx=10, pady=2)
        for i, (lab, dx, dy, dz) in enumerate(
            [("-X", -1, 0, 0), ("+X", 1, 0, 0), ("-Y", 0, -1, 0), ("+Y", 0, 1, 0), ("-Z", 0, 0, -1), ("+Z", 0, 0, 1)]
        ):
            ctk.CTkButton(
                nudge_row,
                text=lab,
                width=42,
                height=24,
                command=lambda a=dx, b=dy, c=dz: self.on_nudge_selection((a, b, c)),
            ).grid(row=0, column=i, padx=1, pady=1)
        ctk.CTkLabel(
            right,
            text="放置/涂改用下方「目标」；笔刷/盒填对破坏·放置·涂改生效。",
            wraplength=280,
            justify="left",
            text_color=("gray40", "gray70"),
            font=ctk.CTkFont(size=11),
        ).grid(row=5, column=0, sticky="w", padx=14, pady=(0, 4))


        brush_row = ctk.CTkFrame(right, fg_color="transparent")
        brush_row.grid(row=6, column=0, sticky="ew", padx=10, pady=2)
        ctk.CTkLabel(brush_row, text="笔刷").pack(side="left", padx=(4, 6))
        self.brush_var = ctk.StringVar(value="小")
        self.brush_seg = ctk.CTkSegmentedButton(
            brush_row,
            values=["小", "中", "大"],
            variable=self.brush_var,
            command=self._on_brush_change,
            width=150,
            height=26,
            font=ctk.CTkFont(size=12),
        )
        self.brush_seg.pack(side="left", padx=2)
        self.box_fill_var = tk.BooleanVar(value=False)
        ctk.CTkCheckBox(
            brush_row,
            text="盒填",
            variable=self.box_fill_var,
            command=self._on_box_fill_toggle,
            width=60,
        ).pack(side="left", padx=(8, 2))

        clip_row = ctk.CTkFrame(right, fg_color="transparent")
        clip_row.grid(row=7, column=0, sticky="ew", padx=10, pady=2)
        ctk.CTkButton(clip_row, text="复制", width=60, height=26, command=self.on_copy_selection).pack(
            side="left", padx=2
        )
        ctk.CTkButton(clip_row, text="剪切", width=60, height=26, command=self.on_cut_selection).pack(
            side="left", padx=2
        )
        ctk.CTkButton(clip_row, text="粘贴", width=60, height=26, command=self.on_paste_at_selection).pack(
            side="left", padx=2
        )
        self.clip_label = ctk.CTkLabel(clip_row, text="剪贴板：空", anchor="w")
        self.clip_label.pack(side="left", padx=6)

        ctk.CTkLabel(right, text="批量方块替换", font=ctk.CTkFont(size=14, weight="bold")).grid(
            row=8, column=0, sticky="w", padx=14, pady=(6, 2)
        )

        self.block_list = ctk.CTkScrollableFrame(right, height=160)
        self.block_list.grid(row=9, column=0, sticky="nsew", padx=10, pady=4)

        self.source_label = ctk.CTkLabel(right, text="源方块：未选择", wraplength=280, justify="left")
        self.source_label.grid(row=10, column=0, sticky="w", padx=14, pady=(8, 2))

        ctk.CTkLabel(right, text="替换目标（可搜索）").grid(
            row=11, column=0, sticky="w", padx=14, pady=(8, 2)
        )
        self.target_filter = ctk.CTkEntry(right, placeholder_text="过滤，如 oak / stone")
        self.target_filter.grid(row=12, column=0, sticky="ew", padx=14, pady=2)
        self.target_filter.bind("<KeyRelease>", lambda _e: self._refresh_target_choices())

        self.target_var = ctk.StringVar(value="")
        self.target_combo = ctk.CTkComboBox(right, variable=self.target_var, values=["(空)"], width=280)
        self.target_combo.grid(row=13, column=0, sticky="ew", padx=14, pady=2)

        ctk.CTkLabel(right, text="常用目标").grid(row=14, column=0, sticky="w", padx=14, pady=(8, 2))
        quick = ctk.CTkFrame(right, fg_color="transparent")
        quick.grid(row=15, column=0, sticky="ew", padx=10, pady=2)
        for i, name in enumerate(QUICK_TARGETS[:6]):
            short = short_block_name(name)
            btn = ctk.CTkButton(
                quick, text=short, width=90, height=26,
                command=lambda n=name: self._set_target(n),
            )
            btn.grid(row=i // 3, column=i % 3, padx=2, pady=2)

        btn_row = ctk.CTkFrame(right, fg_color="transparent")
        btn_row.grid(row=16, column=0, sticky="ew", padx=10, pady=(12, 4))
        self.replace_btn = ctk.CTkButton(btn_row, text="一键替换", command=self.on_replace, width=100)
        self.replace_btn.pack(side="left", padx=2)
        self.undo_btn = ctk.CTkButton(btn_row, text="撤销", command=self.on_undo, width=60, state="disabled")
        self.undo_btn.pack(side="left", padx=2)
        self.redo_btn = ctk.CTkButton(btn_row, text="重做", command=self.on_redo, width=60, state="disabled")
        self.redo_btn.pack(side="left", padx=2)

        save_row = ctk.CTkFrame(right, fg_color="transparent")
        save_row.grid(row=17, column=0, sticky="ew", padx=10, pady=(4, 4))
        ctk.CTkButton(save_row, text="另存为", command=self.on_save_as, width=100).pack(
            side="left", padx=2
        )
        ctk.CTkButton(save_row, text="覆盖保存", command=self.on_save_overwrite, width=100).pack(
            side="left", padx=2
        )

        ctk.CTkLabel(right, text="目标版本（Java）").grid(
            row=18, column=0, sticky="w", padx=14, pady=(10, 2)
        )
        self.export_version_var = ctk.StringVar(value=version_menu_labels()[-1])
        self.export_version_menu = ctk.CTkOptionMenu(
            right,
            variable=self.export_version_var,
            values=version_menu_labels(),
            width=280,
        )
        self.export_version_menu.grid(row=19, column=0, sticky="ew", padx=14, pady=2)
        ctk.CTkLabel(
            right,
            text="生成仍用统一调色板，导出时按版本替换方块",
            wraplength=280,
            justify="left",
            text_color=("gray40", "gray70"),
            font=ctk.CTkFont(size=11),
        ).grid(row=20, column=0, sticky="w", padx=14, pady=(2, 4))

        self.export_bom_var = ctk.BooleanVar(value=True)
        self.export_layers_var = ctk.BooleanVar(value=False)
        bom_opts = ctk.CTkFrame(right, fg_color="transparent")
        bom_opts.grid(row=21, column=0, sticky="ew", padx=10, pady=(4, 0))
        ctk.CTkCheckBox(
            bom_opts,
            text="附带材料清单",
            variable=self.export_bom_var,
            width=140,
        ).pack(side="left", padx=(4, 8))
        ctk.CTkCheckBox(
            bom_opts,
            text="附带分层预览",
            variable=self.export_layers_var,
            width=140,
        ).pack(side="left", padx=4)
        ctk.CTkLabel(
            right,
            text="清单含中文名与箱/盒/组/个；分层会多写 PNG（略慢）",
            wraplength=280,
            justify="left",
            text_color=("gray40", "gray70"),
            font=ctk.CTkFont(size=11),
        ).grid(row=22, column=0, sticky="w", padx=14, pady=(2, 0))

        if not hasattr(self, "open_folder_var"):
            self.open_folder_var = ctk.BooleanVar(value=True)
        ctk.CTkCheckBox(
            right,
            text="导出后打开文件夹",
            variable=self.open_folder_var,
            width=200,
        ).grid(row=23, column=0, sticky="w", padx=14, pady=(6, 0))

        export_row = ctk.CTkFrame(right, fg_color="transparent")
        export_row.grid(row=24, column=0, sticky="ew", padx=10, pady=(6, 6))
        self.export_btn = ctk.CTkButton(
            export_row,
            text="进游戏（导出 PCL）",
            command=self.on_export_to_game,
            width=200,
            height=34,
            font=ctk.CTkFont(weight="bold"),
            fg_color=("#1b7f4a", "#1b7f4a"),
            hover_color=("#146038", "#146038"),
        )
        self.export_btn.pack(side="left")
        # UX_P2_SCHEMES edit-panel

        ctk.CTkLabel(right, text="设计方案", font=ctk.CTkFont(weight="bold")).grid(
            row=25, column=0, sticky="w", padx=14, pady=(12, 2)
        )
        self.scheme_label = ctk.CTkLabel(
            right, text="当前方案：未绑定", anchor="w", wraplength=280
        )
        self.scheme_label.grid(row=26, column=0, sticky="ew", padx=14, pady=2)
        scheme_row1 = ctk.CTkFrame(right, fg_color="transparent")
        scheme_row1.grid(row=27, column=0, sticky="ew", padx=10, pady=(4, 2))
        ctk.CTkButton(
            scheme_row1, text="存为方案", command=self.on_scheme_save_as, width=100
        ).pack(side="left", padx=2)
        ctk.CTkButton(
            scheme_row1, text="保存到方案", command=self.on_scheme_save, width=100
        ).pack(side="left", padx=2)
        scheme_row2 = ctk.CTkFrame(right, fg_color="transparent")
        scheme_row2.grid(row=28, column=0, sticky="ew", padx=10, pady=(2, 2))
        ctk.CTkButton(
            scheme_row2, text="打开方案", command=self.on_scheme_open, width=100
        ).pack(side="left", padx=2)
        ctk.CTkButton(
            scheme_row2, text="导出方案", command=self.on_scheme_export, width=100
        ).pack(side="left", padx=2)
        scheme_row3 = ctk.CTkFrame(right, fg_color="transparent")
        scheme_row3.grid(row=29, column=0, sticky="ew", padx=10, pady=(2, 14))
        ctk.CTkButton(
            scheme_row3,
            text="导入投影到方案",
            command=self.on_scheme_import_litematic,
            width=200,
            fg_color=("#6c3483", "#6c3483"),
        ).pack(side="left", padx=2)

        ctk.CTkLabel(right, text="AI 助手", font=ctk.CTkFont(size=14, weight="bold")).grid(
            row=30, column=0, sticky="w", padx=14, pady=(16, 2)
        )
        ai_row1 = ctk.CTkFrame(right, fg_color="transparent")
        ai_row1.grid(row=31, column=0, sticky="ew", padx=10, pady=2)
        self.furnish_btn = ctk.CTkButton(
            ai_row1, text="自动装修内部", command=self.on_auto_furnish, width=140
        )
        self.furnish_btn.pack(side="left", padx=2)
        ctk.CTkLabel(
            right,
            text="在封闭室内自动放床/箱子/火把/地毯等（可撤销）",
            wraplength=280,
            justify="left",
            text_color=("gray40", "gray70"),
            font=ctk.CTkFont(size=11),
        ).grid(row=32, column=0, sticky="w", padx=14, pady=(0, 4))

        ai_row2 = ctk.CTkFrame(right, fg_color="transparent")
        ai_row2.grid(row=33, column=0, sticky="ew", padx=10, pady=(4, 2))
        self._restyle_label_to_key = {v: k for k, v in STYLE_LABELS.items()}
        self.restyle_var = ctk.StringVar(value=STYLE_LABELS["modern"])
        self.restyle_menu = ctk.CTkOptionMenu(
            ai_row2,
            variable=self.restyle_var,
            values=list(STYLE_LABELS.values()),
            width=110,
        )
        self.restyle_menu.pack(side="left", padx=2)
        self.restyle_btn = ctk.CTkButton(
            ai_row2, text="风格迁移", command=self.on_restyle, width=100
        )
        self.restyle_btn.pack(side="left", padx=2)
        ctk.CTkLabel(
            right,
            text="保留结构，只整体替换材质与外饰（玻璃不动，可撤销）",
            wraplength=280,
            justify="left",
            text_color=("gray40", "gray70"),
            font=ctk.CTkFont(size=11),
        ).grid(row=34, column=0, sticky="w", padx=14, pady=(0, 12))

        ctk.CTkLabel(right, text="对话式局部修改", font=ctk.CTkFont(size=14, weight="bold")).grid(
            row=35, column=0, sticky="w", padx=14, pady=(6, 2)
        )
        self.region_cmd_var = ctk.StringVar()
        self.region_cmd = ctk.CTkEntry(
            right,
            placeholder_text="选中两角后：换成玻璃窗 / 清空 / 铺石砖地板",
            textvariable=self.region_cmd_var,
        )
        self.region_cmd.grid(row=36, column=0, sticky="ew", padx=14, pady=2)
        self.region_cmd.bind("<Return>", lambda _e: self.on_region_command())
        region_row = ctk.CTkFrame(right, fg_color="transparent")
        region_row.grid(row=37, column=0, sticky="ew", padx=10, pady=(2, 2))
        self.region_btn = ctk.CTkButton(
            region_row, text="执行指令", command=self.on_region_command, width=110
        )
        self.region_btn.pack(side="left", padx=2)
        self.region_sel_label = ctk.CTkLabel(
            region_row, text="选区：无", anchor="w", font=ctk.CTkFont(size=11)
        )
        self.region_sel_label.pack(side="left", padx=6)
        ctk.CTkLabel(
            right,
            text="先切「选择」工具点两个对角框出范围，再输入一句指令。只改选区内，可撤销。",
            wraplength=280,
            justify="left",
            text_color=("gray40", "gray70"),
            font=ctk.CTkFont(size=11),
        ).grid(row=38, column=0, sticky="w", padx=14, pady=(0, 12))

        ctk.CTkLabel(right, text="楼层与房间规划", font=ctk.CTkFont(size=14, weight="bold")).grid(
            row=39, column=0, sticky="w", padx=14, pady=(6, 2)
        )
        self.floors_btn = ctk.CTkButton(
            right,
            text="规划楼层与房间",
            command=self.on_plan_floors,
            height=32,
            fg_color=(MC_ACCENT, MC_ACCENT),
            hover_color=(MC_BORDER, MC_BORDER),
            text_color=("#101010", "#101010"),
        )
        self.floors_btn.grid(row=40, column=0, sticky="ew", padx=14, pady=2)
        ctk.CTkLabel(
            right,
            text="自动识别楼板，在每层加隔墙与门洞、开楼梯洞并铺踏步；只动室内，可撤销。",
            wraplength=280,
            justify="left",
            text_color=("gray40", "gray70"),
            font=ctk.CTkFont(size=11),
        ).grid(row=41, column=0, sticky="w", padx=14, pady=(0, 12))

    def _on_mode_change(self, value: str) -> None:
        self._switch_mode(value)

    def _switch_mode(self, mode: str) -> None:
        self._mode = mode
        self.mode_var.set(mode)

        if mode == MODE_EDIT and not getattr(self, "_mat_grid_built", True):
            self._refresh_material_grid()

        for fr in (
            self.browse_frame,
            self.generate_frame,
            self.design_frame,
            self.edit_frame,
            self.tools_frame,
        ):
            fr.grid_forget()

        panels = {
            MODE_BROWSE: (
                self.browse_frame,
                "样本信息",
                "浏览：左栏建筑库点卡片换样本 · 中央拖拽旋转 · 下方步骤条看建造顺序",
            ),
            MODE_GENERATE: (
                self.generate_frame,
                "生成建筑",
                "生成：选 checkpoint / 风格 / 地形点「生成建筑」；或底部一句话速建",
            ),
            MODE_DESIGN: (
                self.design_frame,
                "截图设计",
                "设计：截图+文字 → 条件生成；底部可导入图纸/草图识别成建筑",
            ),
            MODE_EDIT: (
                self.edit_frame,
                "编辑 / 建模",
                "编辑：左键=工具 · 右键=放置 · 1-9 切快捷栏 · 底部 AI 装修/风格迁移",
            ),
            MODE_TOOLS: (
                self.tools_frame,
                "分析工具",
                "工具：Phase1 分析 / Phase3 相似 / Phase4 红石模板 / 一键流水线",
            ),
        }
        frame, title, hint = panels.get(mode, panels[MODE_BROWSE])
        frame.grid(row=0, column=0, sticky="nsew")
        self.inspector_title.configure(text=title)
        self.mode_hint.configure(text=hint)

        if mode == MODE_EDIT:
            self._select_hotbar(self._hotbar_slot)
            self._update_workbench_hint()
            if self.current_voxels is not None:
                self.after(50, lambda: self.render_voxels(self.current_voxels, orbit_lod=False))

        statuses = {
            MODE_BROWSE: "当前在看已有样本",
            MODE_GENERATE: "设置参数后点「生成建筑」",
            MODE_DESIGN: "选截图、写要求，点「理解并生成」",
            MODE_TOOLS: "选参考 .litematic 后执行分析 / 相似 / 红石 / 流水线",
            MODE_EDIT: "编辑：左键工具 / 右键放置 / 1-9 快捷栏",
        }
        self._set_status(statuses.get(mode, "就绪"))

    def _on_num(self, _value: float | None = None) -> None:
        self.num_label.configure(text=str(int(round(self.num_var.get()))))

    def _on_temp(self, _value: float | None = None) -> None:
        self.temp_label.configure(text=f"{float(self.temp_var.get()):.2f}")

    def _on_struct_tries(self, _value: float | None = None) -> None:
        self.struct_tries_label.configure(text=str(int(round(self.struct_tries_var.get()))))

    def _on_rank_num(self, _value: float | None = None) -> None:
        self.rank_num_label.configure(text=f"候选数：{int(round(self.rank_num_var.get()))}")

    def _set_info(self, text: str) -> None:
        self.info_box.configure(state="normal")
        self.info_box.delete("1.0", "end")
        self.info_box.insert("1.0", text)
        self.info_box.configure(state="disabled")

    def _set_status(self, text: str) -> None:
        self.status_var.set(text)

    def _flash_toast(self, text: str, *, ms: int = 900) -> None:
        self._set_status(f"✦ {text}")
        if getattr(self, "_toast_job", None) is not None:
            try:
                self.after_cancel(self._toast_job)
            except Exception:
                pass

        def _restore() -> None:
            self._toast_job = None
            self._update_workbench_hint()

        try:
            self._toast_job = self.after(ms, _restore)
        except Exception:
            self._toast_job = None

    def _build_hotbar(self, parent: ctk.CTkFrame) -> None:
        """底部 MC 物品栏（9 格）+ 工作台提示 + 材质库入口。"""
        wrap = ctk.CTkFrame(parent, fg_color=MC_PANEL_LOW, corner_radius=8)
        wrap.grid(row=2, column=0, sticky="ew", padx=8, pady=(0, 6))
        wrap.grid_columnconfigure(0, weight=1)

        side = ctk.CTkFrame(wrap, fg_color="transparent")
        side.grid(row=0, column=0, sticky="ew", padx=10, pady=(6, 0))

        self.workbench_hint = ctk.CTkLabel(
            side,
            text="",
            anchor="w",
            justify="left",
            wraplength=560,
            font=_font(11),
            text_color=MC_MUTED,
        )
        self.workbench_hint.pack(side="left", fill="x", expand=True)

        hb_row = ctk.CTkFrame(side, fg_color="transparent")
        hb_row.pack(side="right", padx=(8, 0))
        ctk.CTkButton(
            hb_row,
            text="材质库",
            width=84,
            height=24,
            font=_font(11, True),
            fg_color=MC_CARD_ACTIVE,
            hover_color=MC_ACCENT_HOVER,
            text_color=MC_TEXT,
            border_width=1,
            border_color=MC_ACCENT,
            command=self._jump_to_material_picker,
        ).pack(side="left")
        ctk.CTkLabel(
            hb_row,
            text="1-9 切格",
            font=_font(10),
            text_color=MC_MUTED,
        ).pack(side="left", padx=(8, 0))

        bar = ctk.CTkFrame(wrap, fg_color="transparent")
        bar.grid(row=1, column=0, pady=(4, 6))

        self._hotbar_buttons = []
        for i in range(9):
            slot = ctk.CTkFrame(
                bar,
                width=64,
                height=62,
                fg_color=MC_SLOT,
                border_width=2,
                border_color=MC_BORDER,
                corner_radius=6,
            )
            slot.grid(row=0, column=i, padx=2)
            slot.grid_propagate(False)
            num = ctk.CTkLabel(slot, text=str(i + 1), font=_font(10, True), text_color=MC_GOLD)
            num.place(x=4, y=1)
            swatch = ctk.CTkLabel(slot, text="", width=32, height=32, corner_radius=3)
            swatch.place(relx=0.5, rely=0.44, anchor="center")
            namel = ctk.CTkLabel(
                slot, text="", font=_font(9), text_color=MC_MUTED, wraplength=58
            )
            namel.place(relx=0.5, rely=0.83, anchor="center")
            for w in (slot, num, swatch, namel):
                w.bind("<Button-1>", lambda _e, idx=i: self._select_hotbar(idx))
            self._hotbar_buttons.append((slot, swatch, namel))

        self._refresh_hotbar_ui()
        self._update_workbench_hint()

    def _rgb_to_hex(self, rgba: tuple[float, float, float, float]) -> str:
        r, g, b = rgba[0], rgba[1], rgba[2]
        return f"#{int(r * 255):02x}{int(g * 255):02x}{int(b * 255):02x}"

    def _select_hotbar(self, idx: int) -> None:
        self._hotbar_slot = max(0, min(8, int(idx)))
        name = self._hotbar_names[self._hotbar_slot]
        if hasattr(self, "target_var"):
            self._set_target(name)
        self._refresh_hotbar_ui()
        self._update_workbench_hint()

    def _refresh_hotbar_ui(self) -> None:
        if not getattr(self, "_hotbar_buttons", None):
            return
        self._hotbar_images = []
        for i, (slot, swatch, namel) in enumerate(self._hotbar_buttons):
            name = self._hotbar_names[i] if i < len(self._hotbar_names) else "minecraft:stone"
            bid = int(self.name_to_id.get(name, 0) or 0)
            hexc = self._rgb_to_hex(_block_color(bid if bid > 0 else (i + 1)))
            icon = None
            try:
                pil = load_pil_icon(name, size=32)
                if pil is not None and hasattr(ctk, "CTkImage"):
                    icon = ctk.CTkImage(light_image=pil, dark_image=pil, size=(32, 32))
                    self._hotbar_images.append(icon)
            except Exception:
                icon = None
            try:
                if icon is not None:
                    swatch.configure(image=icon, text="", fg_color="transparent")
                else:
                    swatch.configure(image=None, fg_color=hexc, text="")
            except Exception:
                swatch.configure(text="■", text_color=hexc)
            try:
                zh = block_zh_name(name)
            except Exception:
                zh = short_block_name(name)
            namel.configure(text=(zh or short_block_name(name))[:8])
            selected = i == self._hotbar_slot
            slot.configure(
                border_color=MC_GOLD if selected else MC_BORDER,
                border_width=3 if selected else 2,
                fg_color=MC_CARD_ACTIVE if selected else MC_SLOT,
            )

    def _update_workbench_hint(self) -> None:
        if not hasattr(self, "workbench_hint"):
            return
        tool = "?"
        if hasattr(self, "voxel_tool_var"):
            try:
                tool = self.voxel_tool_var.get() or "?"
            except Exception:
                tool = str(getattr(self, "_voxel_tool", "?"))
        tid = None
        tname = "?"
        if hasattr(self, "target_var"):
            tid = self._parse_target_id()
            if tid is not None:
                tname = short_block_name(self.palette.get(tid, str(tid)))
            else:
                tname = short_block_name(self._hotbar_names[self._hotbar_slot])
        else:
            tname = short_block_name(self._hotbar_names[self._hotbar_slot])
            tid = self.name_to_id.get(self._hotbar_names[self._hotbar_slot])
        id_part = f"id={tid}" if tid is not None else "id=?"
        try:
            zh = block_zh_name(self.palette.get(tid, tname) if tid is not None else tname)
        except Exception:
            zh = tname
        tex_note = ""
        info = getattr(self, "_texture_info", None) or {}
        if info.get("ok"):
            tex_note = "  ·  贴图OK"
        elif info:
            tex_note = "  ·  贴图FALLBACK"
        self.workbench_hint.configure(
            text=(
                f"工具 {tool} · 快捷栏[{self._hotbar_slot + 1}] {zh} ({id_part})"
                f"{tex_note} · 左键工具 / 右键放置"
            )
        )

    def _clear_crosshair(self) -> None:
        for art in getattr(self, "_crosshair_artists", []) or []:
            try:
                art.remove()
            except Exception:
                pass
        self._crosshair_artists = []

    def _redraw_crosshair(self) -> None:
        """Center crosshair in figure coords (MC-like +)."""
        self._clear_crosshair()
        if not hasattr(self, "fig"):
            return
        cx, cy, arm = 0.50, 0.50, 0.022
        style = dict(
            transform=self.fig.transFigure,
            color="#f2f2f2",
            linewidth=1.35,
            solid_capstyle="butt",
            zorder=10_000,
            clip_on=False,
        )
        for xs, ys in (([cx - arm, cx + arm], [cy, cy]), ([cx, cx], [cy - arm, cy + arm])):
            ln = Line2D(xs, ys, **style)
            self.fig.add_artist(ln)
            self._crosshair_artists.append(ln)
        # slight gap at center (MC style) via dark overlay stubs
        gap = 0.006
        gap_style = dict(
            transform=self.fig.transFigure,
            color="#1a1a1a",
            linewidth=2.2,
            solid_capstyle="butt",
            zorder=10_001,
            clip_on=False,
        )
        for xs, ys in (([cx - gap, cx + gap], [cy, cy]), ([cx, cx], [cy - gap, cy + gap])):
            ln = Line2D(xs, ys, **gap_style)
            self.fig.add_artist(ln)
            self._crosshair_artists.append(ln)

        # UX P1: block name under crosshair
        label = ""
        try:
            if hasattr(self, "_hotbar_names"):
                raw = self._hotbar_names[self._hotbar_slot]
                label = block_zh_name(raw) or short_block_name(raw)
        except Exception:
            label = ""
        if label:
            txt = self.fig.text(
                cx, cy - 0.055, label,
                transform=self.fig.transFigure, ha="center", va="top",
                color="#f8f8f8", fontsize=9, zorder=10_002, clip_on=False,
                bbox=dict(boxstyle="round,pad=0.2", fc="#00000099", ec="none"),
            )
            self._crosshair_artists.append(txt)
            self._crosshair_label = txt

    def _draw_empty(self) -> None:
        self.ax.clear()
        self.fig.patch.set_facecolor("#87CEEB")
        self.ax.set_facecolor("#87CEEB")
        self.ax.set_title("MC 风格预览（暂无数据）")
        self.ax.set_xlabel("X")
        self.ax.set_ylabel("Z")
        self.ax.set_zlabel("Y")
        if hasattr(self, "canvas"):
            self._redraw_crosshair()

    def _update_info_panel(self) -> None:
        if self.current_voxels is None or self.current_path is None:
            self._set_info("未加载样本")
            return
        vox = self.current_voxels
        non_air = int((vox > 0).sum())
        mc = self.current_path.with_suffix(".mcfunction")
        dirty = "是（未保存）" if self._dirty else "否"
        info = (
            f"文件：{self.current_path.name}\n"
            f"路径：{self.current_path.parent}\n"
            f"形状：{tuple(vox.shape)}\n"
            f"非空气：{non_air}\n"
            f"已修改：{dirty}\n"
            f"mcfunction：{'有' if mc.exists() else '无'}"
        )
        if self._steps:
            info += "\n\n" + stages_summary(self._steps)
        self._set_info(info)

    def refresh_lists(self) -> None:
        try:
            vocab = load_label_vocab()
            styles = vocab.get("styles") or ["medieval"]
            terrains = vocab.get("terrains") or ["flat"]
            self.style_menu.configure(values=styles)
            self.terrain_menu.configure(values=terrains)
            if hasattr(self, "design_style_menu"):
                self.design_style_menu.configure(values=styles)
                self.design_terrain_menu.configure(values=terrains)
            if self.style_var.get() not in styles:
                self.style_var.set("medieval" if "medieval" in styles else styles[0])
            if self.terrain_var.get() not in terrains:
                self.terrain_var.set("flat" if "flat" in terrains else terrains[0])
            if hasattr(self, "design_style_var") and self.design_style_var.get() not in styles:
                self.design_style_var.set("medieval" if "medieval" in styles else styles[0])
            if hasattr(self, "design_terrain_var") and self.design_terrain_var.get() not in terrains:
                self.design_terrain_var.set("flat" if "flat" in terrains else terrains[0])
        except Exception:
            pass

        ckpts = list_checkpoints()
        names = [p.name for p in ckpts] or ["last.pt"]
        self.ckpt_menu.configure(values=names)
        if self.ckpt_var.get() not in names:
            preferred = "cond_last.pt" if "cond_last.pt" in names else names[0]
            self.ckpt_var.set(preferred)

        if hasattr(self, "batch_menu"):
            self.refresh_batch_menu()

        samples = list_sample_files(self.out_dir)
        labels = [p.name for p in samples] or ["(无)"]
        if hasattr(self, "sample_var"):
            cur = self.sample_var.get()
            if cur not in labels:
                self.sample_var.set(labels[0])
        try:
            self._refresh_sample_cards()
        except Exception:
            pass

    def _autoload_first_sample(self) -> None:
        samples = list_sample_files(self.out_dir)
        if samples:
            self.sample_var.set(samples[0].name)
            self.load_and_show(samples[0])

    def on_sample_selected(self, name: str) -> None:
        if not name or name == "(无)":
            return
        if self._dirty:
            if not messagebox.askyesno("未保存", "当前有未保存的修改，切换样本将丢弃修改。继续？"):
                if self.current_path is not None:
                    self.sample_var.set(self.current_path.name)
                return
        path = self.out_dir / name
        if path.exists():
            self.load_and_show(path)

    def load_and_show(self, path: Path) -> None:
        try:
            voxels = load_voxel_npz(path)
        except Exception as exc:  # noqa: BLE001
            self._set_status(f"加载失败：{exc}")
            return
        self.current_voxels = voxels
        self.current_path = path
        self._undo_stack.clear()
        self._dirty = False
        self._source_id = None
        self._sel_pos = None
        self._sel_corner_b = None
        self._box_anchor = None
        self._move_src = None
        self._orbit_lod_active = False
        self._refresh_undo_redo_buttons()
        self.source_label.configure(text="源方块：未选择")
        self.source_label_left.configure(text="源方块：未选择")
        if hasattr(self, "sel_pos_label"):
            self.sel_pos_label.configure(text="选中：无")
        self._update_region_sel_label()
        non_air = int((voxels > 0).sum())
        self._refresh_steps()
        self._update_info_panel()
        self._rebuild_block_list()
        self._mark_sample_card(path)
        self._set_status(f"已加载 {path.name}（non_air={non_air}），正在绘制…")
        self.update_idletasks()
        self.render_voxels(voxels)
        self._set_status(f"已加载 {path.name}（non_air={non_air}）")

    def _on_style_toggle(self) -> None:
        if self.current_voxels is None:
            return
        mode = "性能" if self.style_perf_var.get() else "MC"
        self._set_status(f"切换为{mode}风格预览…")
        self.update_idletasks()
        self.render_voxels(self.current_voxels)
        info = getattr(self, "_last_render_info", {})
        self._set_status(
            f"{mode}风格：面={info.get('faces', '?')} non_air={info.get('non_air', '?')}"
            + ("（已降采样）" if info.get("downsampled") else "")
        )

    def _on_y_slice(self) -> None:
        if self.current_voxels is None:
            return
        self.render_voxels(self.current_voxels)

    def render_voxels(self, voxels: np.ndarray, *, orbit_lod: bool | None = None) -> None:
        perf = bool(self.style_perf_var.get()) if hasattr(self, "style_perf_var") else False
        use_orbit = bool(orbit_lod) if orbit_lod is not None else bool(getattr(self, "_orbit_lod_active", False))
        work = np.asarray(voxels, dtype=np.int16)
        y_cut = int(self.y_slice_var.get()) if hasattr(self, "y_slice_var") else 99
        if work.ndim == 3 and y_cut < work.shape[1] - 1:
            work = work.copy()
            work[:, y_cut + 1 :, :] = 0
        # Collect face meta only when editing (pick) and not in orbit LOD.
        collect = (self._mode == MODE_EDIT) and (not use_orbit)
        draw_edges = bool(getattr(self, "_draw_edges_var", tk.BooleanVar(value=False)).get())
        info = render_mc_voxels(
            self.ax,
            self.fig,
            work,
            self.palette,
            highlight_id=self._source_id,
            highlight_pos=getattr(self, "_sel_pos", None),
            performance=perf,
            orbit_lod=use_orbit,
            preserve_view=True,
            draw_edges=draw_edges,
            collect_meta=collect,
        )
        info = dict(info)
        info["y_slice"] = y_cut
        self._face_meta = list(info.get("face_meta") or [])
        self._redraw_crosshair()
        self.canvas.draw_idle()
        self._last_render_info = info

    def _rebuild_block_list(self) -> None:
        for w in self.block_list.winfo_children():
            w.destroy()
        self._block_buttons.clear()
        if self.current_voxels is None:
            ctk.CTkLabel(self.block_list, text="（无体素）").pack(anchor="w", padx=4, pady=4)
            return
        rows = count_blocks(self.current_voxels, self.palette)
        if not rows:
            ctk.CTkLabel(self.block_list, text="（仅空气）").pack(anchor="w", padx=4, pady=4)
            return
        for row in rows:
            bid = row["id"]
            label = f"[{bid}] {row['short']}  ×{row['count']}"
            selected = self._source_id == bid
            btn = ctk.CTkButton(
                self.block_list,
                text=label,
                anchor="w",
                height=28,
                fg_color=("#1f6aa5", "#1f6aa5") if selected else ("gray25", "gray25"),
                command=lambda b=bid, n=row["name"]: self._select_source(b, n),
            )
            btn.pack(fill="x", padx=2, pady=1)
            self._block_buttons.append(btn)

    def _select_source(self, block_id: int, name: str) -> None:
        self._source_id = int(block_id)
        text = f"源方块：[{block_id}] {short_block_name(name)}"
        self.source_label.configure(text=text)
        self.source_label_left.configure(text=text)
        self._rebuild_block_list()
        if self.current_voxels is not None:
            self.render_voxels(self.current_voxels)
        self._set_status(f"已选源方块 [{block_id}] {short_block_name(name)}")

    def _palette_choices(self, filter_text: str = "") -> list[str]:
        q = filter_text.strip().lower()
        items: list[str] = []
        for bid in sorted(self.palette):
            if bid <= 0:
                continue
            name = self.palette[bid]
            short = short_block_name(name)
            label = f"[{bid}] {short}"
            if not q or q in short.lower() or q in name.lower() or q == str(bid):
                items.append(label)
        return items or ["(无匹配)"]

    def _refresh_target_choices(self) -> None:
        filt = ""
        try:
            filt = self.target_filter.get()
        except Exception:  # noqa: BLE001
            pass
        values = self._palette_choices(filt)
        self.target_combo.configure(values=values)
        cur = self.target_var.get()
        if cur not in values:
            self.target_var.set(values[0])

    def _set_target(self, full_name: str) -> None:
        bid = self.name_to_id.get(full_name)
        if bid is None:
            self._set_status(f"palette 中无：{full_name}")
            return
        label = f"[{bid}] {short_block_name(full_name)}"
        values = list(self.target_combo.cget("values") or [])
        if label not in values:
            values = [label] + [v for v in values if v != "(无匹配)"]
            self.target_combo.configure(values=values)
        self.target_var.set(label)
        # keep hotbar highlight in sync when target matches a slot
        for i, n in enumerate(self._hotbar_names):
            bid = self.name_to_id.get(n)
            if bid is not None and f"[{bid}]" in label:
                self._hotbar_slot = i
                break
        self._refresh_hotbar_ui()
        self._update_workbench_hint()
        self._set_status(f"目标设为 {label}")

    def _parse_target_id(self) -> int | None:
        raw = (self.target_var.get() or "").strip()
        if not raw or raw.startswith("(无"):
            return None
        if raw.startswith("[") and "]" in raw:
            try:
                return int(raw[1 : raw.index("]")])
            except ValueError:
                return None
        if raw.isdigit():
            return int(raw)
        name = raw if ":" in raw else f"minecraft:{raw}"
        return self.name_to_id.get(name)

    def on_replace(self) -> None:
        if self.current_voxels is None:
            self._set_status("请先加载样本")
            return
        if self._source_id is None:
            self._set_status("请先在列表中选择源方块")
            return
        target_id = self._parse_target_id()
        if target_id is None:
            self._set_status("请选择有效的目标方块")
            return
        if target_id == self._source_id:
            self._set_status("源与目标相同，无需替换")
            return

        self._push_undo()
        new_vox, n = replace_block_id(self.current_voxels, self._source_id, target_id)
        if n == 0:
            self._set_status("没有可替换的体素")
            self._undo_stack._undo.pop()  # discard empty push
            return
        self.current_voxels = new_vox
        self._dirty = True
        self._refresh_undo_redo_buttons()
        src_name = short_block_name(self.palette.get(self._source_id, str(self._source_id)))
        tgt_name = short_block_name(self.palette.get(target_id, str(target_id)))
        self._source_id = None
        self.source_label.configure(text="源方块：未选择（刚完成替换）")
        self.source_label_left.configure(text="源方块：未选择（刚完成替换）")
        self._rebuild_block_list()
        self._update_info_panel()
        self.render_voxels(self.current_voxels)
        self._set_status(f"已替换 {n} 格：{src_name} → {tgt_name}（可撤销 / 记得保存）")

    def on_undo(self) -> None:
        if self.current_voxels is None or not self._undo_stack.can_undo():
            self._set_status("没有可撤销的操作")
            return
        restored = self._undo_stack.undo(self.current_voxels)
        if restored is None:
            self._set_status("没有可撤销的操作")
            return
        self.current_voxels = restored
        self._dirty = True
        self._source_id = None
        self.source_label.configure(text="源方块：未选择")
        self.source_label_left.configure(text="源方块：未选择")
        self._refresh_undo_redo_buttons()
        self._rebuild_block_list()
        self._update_info_panel()
        self.render_voxels(self.current_voxels)
        self._set_status(
            f"已撤销（还可撤 {self._undo_stack.undo_len}，重做 {self._undo_stack.redo_len}）"
        )

    def on_redo(self) -> None:
        if self.current_voxels is None or not self._undo_stack.can_redo():
            self._set_status("没有可重做的操作")
            return
        restored = self._undo_stack.redo(self.current_voxels)
        if restored is None:
            self._set_status("没有可重做的操作")
            return
        self.current_voxels = restored
        self._dirty = True
        self._refresh_undo_redo_buttons()
        self._rebuild_block_list()
        self._update_info_panel()
        self.render_voxels(self.current_voxels)
        self._set_status(
            f"已重做（还可撤 {self._undo_stack.undo_len}，重做 {self._undo_stack.redo_len}）"
        )

    def on_save_as(self) -> None:
        if self.current_voxels is None:
            self._set_status("没有可保存的体素")
            return
        path = next_edit_path(self.out_dir)
        try:
            meta = save_voxels_pair(self.current_voxels, self.palette, path)
        except Exception as exc:  # noqa: BLE001
            self._set_status(f"保存失败：{exc}")
            messagebox.showerror("保存失败", str(exc))
            return
        self.current_path = meta["npz_path"]
        self._dirty = False
        self._undo_stack.clear()
        self._refresh_undo_redo_buttons()
        self.refresh_lists()
        self.sample_var.set(self.current_path.name)
        self._update_info_panel()
        self._set_status(f"已另存为 {self.current_path.name}（non_air={meta['non_air']}）")

    def on_save_overwrite(self) -> None:
        if self.current_voxels is None or self.current_path is None:
            self._set_status("没有可保存的体素")
            return
        if not messagebox.askyesno(
            "覆盖确认",
            f"将覆盖：\n{self.current_path}\n以及同名 .mcfunction\n\n确定？",
        ):
            return
        try:
            meta = save_voxels_pair(self.current_voxels, self.palette, self.current_path)
        except Exception as exc:  # noqa: BLE001
            self._set_status(f"保存失败：{exc}")
            messagebox.showerror("保存失败", str(exc))
            return
        self._dirty = False
        self._undo_stack.clear()
        self._refresh_undo_redo_buttons()
        self._update_info_panel()
        self._set_status(f"已覆盖保存 {self.current_path.name}（non_air={meta['non_air']}）")

    def on_auto_furnish(self) -> None:
        """AI 助手：给当前建筑自动放内饰（可撤销）。"""
        if self.current_voxels is None:
            self._set_status("请先加载一个样本")
            return
        try:
            arr, placements = furnish(self.current_voxels, self.palette)
        except Exception as exc:  # noqa: BLE001
            self._set_status(f"自动装修失败：{exc}")
            messagebox.showerror("自动装修失败", str(exc))
            return
        if not placements:
            self._set_status("没找到可装修的室内空间（需要相对封闭的房间）")
            return
        self._push_undo()
        self.current_voxels = arr
        summary = furnish_summary(placements)
        self._after_voxel_edit(f"自动装修：{summary}")
        self._set_status(f"自动装修完成：{summary}（记得另存）")

    def on_restyle(self) -> None:
        """AI 助手：整体风格迁移，保留结构只换材质（可撤销）。"""
        if self.current_voxels is None:
            self._set_status("请先加载一个样本")
            return
        label = self.restyle_var.get()
        target = self._restyle_label_to_key.get(label, "modern")
        try:
            arr, stats = restyle(self.current_voxels, self.palette, target)
        except Exception as exc:  # noqa: BLE001
            self._set_status(f"风格迁移失败：{exc}")
            messagebox.showerror("风格迁移失败", str(exc))
            return
        if stats["changed"] == 0:
            self._set_status(f"风格迁移：没有可替换的方块（目标 {label}）")
            return
        self._push_undo()
        self.current_voxels = arr
        self._after_voxel_edit(f"风格迁移 → {label}")
        self._set_status(
            f"风格迁移 → {label}：替换 {stats['changed']} 格（{stats['map_size']} 条规则，记得另存）"
        )

    def _region_box(self) -> tuple[tuple[int, int, int], tuple[int, int, int]] | None:
        if self._sel_pos is None:
            return None
        return self._sel_pos, (self._sel_corner_b or self._sel_pos)

    def _update_region_sel_label(self) -> None:
        if not hasattr(self, "region_sel_label"):
            return
        box = self._region_box()
        if box is None:
            self.region_sel_label.configure(text="选区：无（点两个对角）")
            return
        a, b = box
        if self._sel_corner_b is None:
            self.region_sel_label.configure(text=f"选区：{a} 单格")
            return
        sx = abs(a[0] - b[0]) + 1
        sy = abs(a[1] - b[1]) + 1
        sz = abs(a[2] - b[2]) + 1
        self.region_sel_label.configure(text=f"选区：{sx}×{sy}×{sz}")

    def on_region_command(self) -> None:
        """对话式局部修改：把一句指令作用在当前选区。"""
        if self.current_voxels is None:
            self._set_status("请先加载一个样本")
            return
        box = self._region_box()
        if box is None:
            self._set_status("请先用「选择」工具点两个对角框出选区")
            messagebox.showinfo("局部修改", "先用「选择」工具在建筑上点两个对角，框出要改的范围。")
            return
        text = self.region_cmd_var.get().strip()
        if not text:
            self._set_status("请输入一句指令，例如：换成玻璃窗")
            return
        try:
            solid = self.current_voxels[self.current_voxels > 0]
            dominant = int(np.bincount(solid).argmax()) if solid.size else None
            op = parse_instruction(text, self.palette, fallback_material=dominant)
            arr, info = apply_region_op(self.current_voxels, self.palette, box, op)
        except Exception as exc:  # noqa: BLE001
            self._set_status(f"指令未执行：{exc}")
            messagebox.showwarning("指令未识别", str(exc))
            return
        if info["changed"] == 0:
            self._set_status(f"「{text}」没有改动任何方块（选区里可能已经是目标材质）")
            return
        self._push_undo()
        self.current_voxels = arr
        self._after_voxel_edit(f"{op['note']}：{info['changed']} 格")
        self._set_status(f"{op['note']}：改动 {info['changed']} 格（可撤销）")

    def on_plan_floors(self) -> None:
        """楼层与房间规划：隔墙、门洞、楼梯。"""
        if self.current_voxels is None:
            self._set_status("请先加载一个样本")
            return
        try:
            arr, info = plan_floors(self.current_voxels, self.palette)
        except Exception as exc:  # noqa: BLE001
            self._set_status(f"规划失败：{exc}")
            messagebox.showwarning("无法规划", str(exc))
            return
        if not info["walls"] and not info["stairs"]:
            self._set_status("没有可分割的室内空间（这栋建筑是实心体量）")
            return
        self._push_undo()
        self.current_voxels = arr
        msg = floors_summary(info)
        self._after_voxel_edit(msg)
        self._set_status(f"{msg}（可撤销）")

    def on_generate(self) -> None:
        if self._generating:
            return
        if self._dirty:
            if not messagebox.askyesno("未保存", "当前有未保存的修改，生成会切换到新样本。继续？"):
                return
        ckpt_name = self.ckpt_var.get()
        ckpt = self.root_dir / "checkpoints" / ckpt_name
        if not ckpt.exists():
            self._set_status(f"找不到 checkpoint：{ckpt}")
            return

        num = int(round(self.num_var.get()))
        rank_on = bool(self.rank_var.get()) if hasattr(self, "rank_var") else False
        if rank_on:
            num = max(num, int(round(self.rank_num_var.get())))
        temp = float(self.temp_var.get())
        self._generating = True
        self.gen_btn.configure(state="disabled", text="生成中…")
        sc = "结构约束开" if self.struct_var.get() else "结构约束关"
        look = "细节增强开" if self.look_harden_var.get() else "细节增强关"
        retry = int(round(self.struct_tries_var.get()))
        self._set_status(
            f"正在生成 num={num} temp={temp:.2f} {sc}/{look}/重试{retry}…（后台，请稍候）"
        )

        def worker() -> None:
            err: Exception | None = None
            results = None
            try:
                results = generate_samples(
                    num=num,
                    temperature=temp,
                    checkpoint=ckpt,
                    out_dir=self.out_dir,
                    style=self.style_var.get(),
                    terrain=self.terrain_var.get(),
                    structure_constrain=bool(self.struct_var.get()),
                    structure_mode=str(self.struct_mode_var.get()),
                    structure_max_tries=int(round(self.struct_tries_var.get())),
                    look_harden_enable=bool(self.look_harden_var.get()),
                    preserve_windows=bool(self.preserve_windows_var.get()),
                    place_window_glass=bool(self.window_glass_var.get()),
                )
            except Exception as exc:  # noqa: BLE001
                err = exc

            def done() -> None:
                self._generating = False
                self.gen_btn.configure(state="normal", text="生成建筑")
                self.refresh_lists()
                if err is not None:
                    self._set_status(f"生成失败：{err}")
                    messagebox.showerror("生成失败", str(err))
                    return
                assert results is not None
                ranked = rank_results(results) if rank_on else []
                best = ranked[0] if ranked else results[0]
                self._switch_mode(MODE_BROWSE)
                self.sample_var.set(best["npz_path"].name)
                if ranked:
                    top = "；".join(f"#{r['index']} {r['total']:.1f}分" for r in ranked[:3])
                    self._set_status(
                        f"生成 {len(ranked)} 张，择优打开最高分（{top}），其余在建筑库"
                    )
                else:
                    summary = "；".join(f"#{r['index']} non_air={r['non_air']}" for r in results)
                    self._set_status(f"生成完成：{summary}")
                self.load_and_show(best["npz_path"])

            self.after(0, done)

        threading.Thread(target=worker, daemon=True).start()

    def on_quick_build(self) -> None:
        """生成页：一句话文字速建（文字 → 设计规格 → 条件生成）。"""
        if self._generating:
            return
        text = self.quick_text_var.get().strip()
        if not text:
            self._set_status("请先输入一句话描述，例如：带塔楼的中世纪石堡")
            return
        if self._dirty:
            if not messagebox.askyesno("未保存", "当前有未保存的修改，生成会切换到新样本。继续？"):
                return
        ckpt = self.root_dir / "checkpoints" / "cond_last.pt"
        if not ckpt.exists():
            alt = self.root_dir / "checkpoints" / self.ckpt_var.get()
            ckpt = alt if alt.exists() else ckpt
        if not ckpt.exists():
            self._set_status(f"找不到条件权重：{ckpt}")
            messagebox.showerror("生成失败", f"找不到 checkpoint：\n{ckpt}")
            return

        num = int(round(self.num_var.get()))
        temp = float(self.temp_var.get())
        self._generating = True
        self.quick_build_btn.configure(state="disabled", text="速建中…")
        self._set_status(f"文字速建中：{text} …（后台，请稍候）")

        def worker() -> None:
            err: Exception | None = None
            results = None
            spec: DesignSpec | None = None
            try:
                spec = infer_design_spec(text_brief=text, prefer_api=True)
                results = generate_from_design(
                    spec,
                    num=num,
                    temperature=temp,
                    checkpoint=ckpt,
                    out_dir=self.out_dir,
                )
            except Exception as exc:  # noqa: BLE001
                err = exc

            def done() -> None:
                self._generating = False
                self.quick_build_btn.configure(state="normal", text="速建")
                self.refresh_lists()
                if err is not None:
                    self._set_status(f"速建失败：{err}")
                    messagebox.showerror("速建失败", str(err))
                    return
                assert results is not None and spec is not None
                first = results[0]
                self._switch_mode(MODE_BROWSE)
                self.sample_var.set(first["npz_path"].name)
                summary = "；".join(f"#{r['index']} non_air={r['non_air']}" for r in results)
                self._set_status(
                    f"速建完成 [{spec.style}/{spec.terrain}]：{summary}"
                )
                self.load_and_show(first["npz_path"])

            self.after(0, done)

        threading.Thread(target=worker, daemon=True).start()


    def on_batch_build(self) -> None:
        """生成页：按多行描述批量各生成一座建筑。"""
        if self._generating:
            return
        raw = self.batch_text.get("1.0", "end") if hasattr(self, "batch_text") else ""
        descs = [ln.strip() for ln in str(raw).splitlines() if ln.strip()]
        if len(descs) > 6:
            descs = descs[:6]
            self._set_status("批量速建：只取前 6 条")
        if not descs:
            self._set_status("请至少写一条描述（每行一条）")
            return
        if self._dirty:
            if not messagebox.askyesno("未保存", "当前有未保存的修改，生成会切换到新样本。继续？"):
                return
        ckpt = self.root_dir / "checkpoints" / "cond_last.pt"
        if not ckpt.exists():
            alt = self.root_dir / "checkpoints" / self.ckpt_var.get()
            ckpt = alt if alt.exists() else ckpt
        if not ckpt.exists():
            self._set_status(f"找不到条件权重：{ckpt}")
            messagebox.showerror("生成失败", f"找不到 checkpoint：\n{ckpt}")
            return

        temp = float(self.temp_var.get())
        self._generating = True
        self.batch_btn.configure(state="disabled", text="批量中…")
        self._set_status(f"批量速建 {len(descs)} 条…（后台，请稍候）")

        def worker() -> None:
            done_items: list[dict] = []
            errors: list[str] = []
            for i, desc in enumerate(descs):
                try:
                    spec = infer_design_spec(text_brief=desc, prefer_api=True)
                    rs = generate_from_design(
                        spec,
                        num=1,
                        temperature=temp,
                        checkpoint=ckpt,
                        out_dir=self.out_dir,
                        seed=1000 + i * 13,  # 每条不同种子，避免批量出同一座
                    )
                    first = rs[0]
                    done_items.append(
                        {
                            "desc": desc,
                            "style": spec.style,
                            "terrain": spec.terrain,
                            "npz_path": first["npz_path"],
                            "non_air": first["non_air"],
                        }
                    )
                except Exception as exc:  # noqa: BLE001
                    errors.append(f"{desc}：{exc}")

            def done() -> None:
                self._generating = False
                self.batch_btn.configure(state="normal", text="批量速建")
                self.refresh_lists()
                if not done_items:
                    self._set_status("批量速建全部失败：" + "；".join(errors))
                    messagebox.showerror("批量速建失败", "\n".join(errors) or "没有结果")
                    return
                self._switch_mode(MODE_BROWSE)
                self.sample_var.set(done_items[0]["npz_path"].name)
                self.load_and_show(done_items[0]["npz_path"])
                summary = "；".join(
                    f"{d['desc'][:8]}→{d['style']}/{d['terrain']}({d['non_air']})"
                    for d in done_items
                )
                extra = f"；失败 {len(errors)} 条" if errors else ""
                self._set_status(f"批量速建完成 {len(done_items)}/{len(descs)}：{summary}{extra}")

            self.after(0, done)

        threading.Thread(target=worker, daemon=True).start()


    def on_pick_design_image(self) -> None:
        path = filedialog.askopenfilename(
            title="选择 Minecraft 截图",
            filetypes=[
                ("图片", "*.png;*.jpg;*.jpeg;*.webp;*.bmp"),
                ("PNG", "*.png"),
                ("JPEG", "*.jpg;*.jpeg"),
                ("全部", "*.*"),
            ],
        )
        if not path:
            return
        self._design_image_path = Path(path)
        self.design_image_var.set(self._design_image_path.name)
        self._set_status(f"已选截图：{self._design_image_path.name}")

    def on_clear_design_image(self) -> None:
        self._design_image_path = None
        self.design_image_var.set("未选择截图")
        self._set_status("已清除截图")

    def _read_design_text(self) -> str:
        try:
            return self.design_text.get("1.0", "end").strip()
        except Exception:  # noqa: BLE001
            return ""

    def _show_design_spec(self, spec: DesignSpec) -> None:
        self._last_design_spec = spec
        self.design_style_var.set(spec.style)
        self.design_terrain_var.set(spec.terrain)
        src_label = "视觉 API" if spec.source == "openai" else "启发式"
        self.design_meta_var.set(
            f"来源：{src_label} · 置信度 {spec.confidence:.0%} · 可手改上方风格/地形"
        )
        self.design_spec_box.configure(state="normal")
        self.design_spec_box.delete("1.0", "end")
        self.design_spec_box.insert("1.0", format_spec_for_ui(spec))
        self.design_spec_box.configure(state="disabled")

    def _build_spec_from_ui(self, *, run_infer: bool) -> DesignSpec:
        text = self._read_design_text()
        image = self._design_image_path
        if run_infer:
            spec = infer_design_spec(
                text_brief=text,
                image_path=image,
                prefer_api=True,
            )
        elif self._last_design_spec is not None:
            spec = DesignSpec(**self._last_design_spec.to_dict())
            spec.text_brief = text
            spec.screenshot_path = str(image) if image else spec.screenshot_path
        else:
            spec = DesignSpec(
                style=self.design_style_var.get(),
                terrain=self.design_terrain_var.get(),
                prompt_summary=text[:160],
                text_brief=text,
                screenshot_path=str(image) if image else None,
                source="manual",
                confidence=0.5,
                notes="未跑理解，使用当前下拉选项",
            )
        # 始终以界面下拉为准（用户可覆盖）
        spec.style = self.design_style_var.get()
        spec.terrain = self.design_terrain_var.get()
        return spec

    def on_design_understand(self) -> None:
        text = self._read_design_text()
        if not text and self._design_image_path is None:
            self._set_status("请先选择截图或填写文字要求")
            messagebox.showinfo("设计", "请至少提供截图或文字要求之一。")
            return
        self._set_status("正在理解要求…")
        self.update_idletasks()
        try:
            spec = infer_design_spec(
                text_brief=text,
                image_path=self._design_image_path,
                prefer_api=True,
            )
        except Exception as exc:  # noqa: BLE001
            self._set_status(f"理解失败：{exc}")
            messagebox.showerror("理解失败", str(exc))
            return
        self._show_design_spec(spec)
        self._set_status(
            f"已理解 → {spec.style}/{spec.terrain}（{spec.source} {spec.confidence:.0%}），可手改后生成"
        )

    def on_design_generate(self) -> None:
        if self._generating:
            return
        text = self._read_design_text()
        if not text and self._design_image_path is None and self._last_design_spec is None:
            self._set_status("请先选择截图或填写文字要求")
            messagebox.showinfo("设计", "请至少提供截图或文字要求之一。")
            return
        if self._dirty:
            if not messagebox.askyesno("未保存", "当前有未保存的修改，生成会切换到新样本。继续？"):
                return

        # 若还没理解过，先理解；已理解则沿用并套用下拉覆盖
        need_infer = self._last_design_spec is None
        if need_infer:
            self._set_status("正在理解要求…")
            self.update_idletasks()
            try:
                spec = infer_design_spec(
                    text_brief=text,
                    image_path=self._design_image_path,
                    prefer_api=True,
                )
            except Exception as exc:  # noqa: BLE001
                self._set_status(f"理解失败：{exc}")
                messagebox.showerror("理解失败", str(exc))
                return
            self._show_design_spec(spec)
        else:
            spec = DesignSpec(**self._last_design_spec.to_dict())
            spec.text_brief = text
            if self._design_image_path is not None:
                spec.screenshot_path = str(self._design_image_path)

        # 用户手改优先
        spec.style = self.design_style_var.get()
        spec.terrain = self.design_terrain_var.get()
        self._show_design_spec(spec)

        ckpt = self.root_dir / "checkpoints" / "cond_last.pt"
        if not ckpt.exists():
            # 回退到生成页所选 checkpoint
            alt = self.root_dir / "checkpoints" / self.ckpt_var.get()
            ckpt = alt if alt.exists() else ckpt
        if not ckpt.exists():
            self._set_status(f"找不到条件权重：{ckpt}")
            messagebox.showerror("生成失败", f"找不到 checkpoint：\n{ckpt}")
            return

        num = int(round(self.num_var.get())) if hasattr(self, "num_var") else 1
        temp = float(self.temp_var.get()) if hasattr(self, "temp_var") else 1.0
        self._generating = True
        self.design_gen_btn.configure(state="disabled", text="生成中…")
        self.design_understand_btn.configure(state="disabled")
        self._set_status(
            f"设计生成中 style={spec.style} terrain={spec.terrain} …（后台）"
        )

        def worker() -> None:
            err: Exception | None = None
            results = None
            try:
                results = generate_from_design(
                    spec,
                    num=num,
                    temperature=temp,
                    checkpoint=ckpt,
                    out_dir=self.out_dir,
                )
            except Exception as exc:  # noqa: BLE001
                err = exc

            def done() -> None:
                self._generating = False
                self.design_gen_btn.configure(state="normal", text="理解并生成")
                self.design_understand_btn.configure(state="normal")
                self.refresh_lists()
                if err is not None:
                    self._set_status(f"设计生成失败：{err}")
                    messagebox.showerror("生成失败", str(err))
                    return
                assert results is not None
                first = results[0]
                self._switch_mode(MODE_BROWSE)
                self.sample_var.set(first["npz_path"].name)
                summary = "；".join(f"#{r['index']} non_air={r['non_air']}" for r in results)
                self._set_status(
                    f"设计完成 [{spec.style}/{spec.terrain}]：{summary}"
                )
                self.load_and_show(first["npz_path"])

            self.after(0, done)

        threading.Thread(target=worker, daemon=True).start()

    def on_import_blueprint(self) -> None:
        """设计页：导入图纸/草图 → 识别轮廓 → 拉起建筑壳 → 保存并打开。"""
        if self.current_voxels is not None and self._dirty:
            if not messagebox.askyesno("未保存", "当前有未保存的修改，导入图纸会切换到新样本。继续？"):
                return
        path = filedialog.askopenfilename(
            title="选择图纸 / 草图（平面图）",
            filetypes=[
                ("图片", "*.png *.jpg *.jpeg *.bmp *.webp"),
                ("所有文件", "*.*"),
            ],
        )
        if not path:
            return
        style = self.design_style_var.get() or "medieval"
        try:
            vox, info = build_from_image(path, self.palette, height=10, style=style)
        except Exception as exc:  # noqa: BLE001
            self._set_status(f"图纸识别失败：{exc}")
            messagebox.showerror("图纸识别失败", str(exc))
            return
        try:
            meta = save_voxels_pair(vox, self.palette, next_edit_path(self.out_dir))
        except Exception as exc:  # noqa: BLE001
            self._set_status(f"保存失败：{exc}")
            messagebox.showerror("保存失败", str(exc))
            return
        self.refresh_lists()
        self._switch_mode(MODE_BROWSE)
        self.sample_var.set(meta["npz_path"].name)
        kind = "线稿" if info["mode"] == "line" else "剪影"
        close_label = {"closed": "闭环", "bridged": "缺口自动闭合", "hull": "凸包闭合", "open": "未能闭合"}.get(
            info.get("close", ""), ""
        )
        extra = f"，{close_label}" if close_label else ""
        self._set_status(
            f"图纸→建筑（{kind}，占地 {info['fill']:.0%}，高 {info['height']}，"
            f"non_air={info['non_air']}{extra}）：{meta['npz_path'].name}"
        )
        self.load_and_show(meta["npz_path"])

    def _export_bom_enabled(self) -> bool:
        return bool(getattr(self, "export_bom_var", None) and self.export_bom_var.get())

    def _export_layers_enabled(self) -> bool:
        return bool(getattr(self, "export_layers_var", None) and self.export_layers_var.get())

    def _write_export_bom(
        self,
        voxels: np.ndarray,
        litematic_path: Path | str,
        *,
        source: str | None = None,
        extra: dict | None = None,
    ) -> dict:
        """Sidecar BOM (+ optional layers) next to the .litematic. Soft-fail."""
        if not self._export_bom_enabled():
            return {"skipped": True}
        try:
            return write_export_sidecars(
                voxels,
                self.palette,
                litematic_path,
                with_bom=True,
                with_layers=self._export_layers_enabled(),
                source=source,
                extra=extra,
            )
        except Exception as exc:  # noqa: BLE001
            return {"skipped": False, "error": str(exc)}

    def on_export_litematic(self) -> None:
        if self.current_voxels is None:
            self._set_status("没有可导出的体素，请先加载或生成建筑")
            return
        base = "ai_preview"
        if self.current_path is not None:
            stem = self.current_path.stem
            if stem.endswith(".npz"):
                stem = Path(stem).stem
            base = f"ai_{stem}"
        label = ""
        if hasattr(self, "export_version_var"):
            label = self.export_version_var.get()
        target = version_id_from_menu_label(label) if label else DEFAULT_VERSION_ID
        try:
            ver = get_version(target)
            info = export_voxels_to_companion(
                self.current_voxels,
                self.palette,
                name=base,
                target_version=target,
            )
        except Exception as exc:  # noqa: BLE001
            self._set_status(f"导出失败：{exc}")
            messagebox.showerror("导出失败", str(exc))
            return
        path = info["path"]
        schematics_dir_note = info.get("schematics_dir") or resolve_schematics_dir()
        remap_n = info.get("remap_changed_pairs", 0)
        bom_info = self._write_export_bom(
            self.current_voxels,
            path,
            source=str(self.current_path) if self.current_path else base,
            extra={
                "litematic": str(path),
                "target_version": info.get("target_version"),
            },
        )
        bom_note = f"\n目标目录：{schematics_dir_note}"
        if bom_info.get("error"):
            bom_note = f"\n材料清单写入失败：{bom_info['error']}"
        elif not bom_info.get("skipped"):
            md = (bom_info.get("bom_paths") or {}).get("md", "")
            totals = bom_info.get("totals") or {}
            bom_note = (
                f"\n材料清单：{md}"
                f"（种类 {totals.get('unique_blocks', '?')}，"
                f"块数 {totals.get('total_blocks', '?')}）"
            )
            if bom_info.get("layers"):
                html = (bom_info["layers"] or {}).get("html")
                if html:
                    bom_note += f"\n分层预览：{html}"
        self._set_status(
            f"已导出 {path}（目标 {info.get('target_display', ver.display_name)}，"
            f"替换 {remap_n} 种，non_air={info['non_air']}）。"
            f"对 Andy 说：列出投影 / 加载 {info['name']}"
            + (bom_note.replace("\n", "；") if bom_note else "")
        )
        messagebox.showinfo(
            "导出成功",
            f"已写入：\n{path}\n\n"
            f"目标版本：{info.get('target_display', target)}（Java）\n"
            f"方块替换种类：{remap_n}\n"
            f"非空方块：{info['non_air']}"
            f"{bom_note}\n\n"
            f"在游戏里对 Andy 说「列出投影」或「加载 {info['name']}」。",
        )



    def _build_tools_panel(self, parent: ctk.CTkFrame) -> None:
        parent.grid_columnconfigure(0, weight=1)
        parent.grid_rowconfigure(0, weight=1)
        scroll = ctk.CTkScrollableFrame(parent, fg_color="transparent")
        scroll.grid(row=0, column=0, sticky="nsew")
        scroll.grid_columnconfigure(0, weight=1)
        parent = scroll

        self._tools_last_report: Path | None = None
        self._tools_busy = False

        ctk.CTkLabel(parent, text="参考 .litematic", font=ctk.CTkFont(weight="bold")).grid(
            row=0, column=0, sticky="w", padx=4, pady=(4, 2)
        )
        self.tools_ref_var = ctk.StringVar(value="")
        ctk.CTkEntry(parent, textvariable=self.tools_ref_var).grid(
            row=1, column=0, sticky="ew", padx=4, pady=2
        )
        ctk.CTkButton(parent, text="浏览…", command=self._tools_pick_litematic, height=28).grid(
            row=2, column=0, sticky="ew", padx=4, pady=(2, 8)
        )

        ctk.CTkLabel(parent, text="① 分析（Phase1）", font=ctk.CTkFont(weight="bold")).grid(
            row=3, column=0, sticky="w", padx=4, pady=(8, 2)
        )
        ctk.CTkLabel(
            parent,
            text="结构/风格/红石 D1–D9 + 刻仿真报告",
            wraplength=250,
            justify="left",
            text_color=("gray40", "gray70"),
            font=ctk.CTkFont(size=12),
        ).grid(row=4, column=0, sticky="w", padx=4)
        row_a = ctk.CTkFrame(parent, fg_color="transparent")
        row_a.grid(row=5, column=0, sticky="ew", padx=4, pady=4)
        row_a.grid_columnconfigure((0, 1), weight=1)
        self.analyze_btn = ctk.CTkButton(row_a, text="分析", command=self.on_tools_analyze, height=32)
        self.analyze_btn.grid(row=0, column=0, sticky="ew", padx=(0, 4))
        self.open_report_btn = ctk.CTkButton(
            row_a, text="打开报告", command=self.on_tools_open_report, height=32
        )
        self.open_report_btn.grid(row=0, column=1, sticky="ew", padx=(4, 0))

        ctk.CTkLabel(parent, text="② 入库 / 相似变体（Phase3）", font=ctk.CTkFont(weight="bold")).grid(
            row=6, column=0, sticky="w", padx=4, pady=(14, 2)
        )
        ctk.CTkLabel(parent, text="相似数量 (1–4)").grid(row=7, column=0, sticky="w", padx=4, pady=(4, 2))
        self.tools_sim_num = ctk.IntVar(value=1)
        ctk.CTkSlider(
            parent, from_=1, to=4, number_of_steps=3, variable=self.tools_sim_num
        ).grid(row=8, column=0, sticky="ew", padx=4, pady=2)
        row_s = ctk.CTkFrame(parent, fg_color="transparent")
        row_s.grid(row=9, column=0, sticky="ew", padx=4, pady=4)
        row_s.grid_columnconfigure((0, 1), weight=1)
        self.ingest_btn = ctk.CTkButton(row_s, text="入库特征", command=self.on_tools_ingest, height=32)
        self.ingest_btn.grid(row=0, column=0, sticky="ew", padx=(0, 4))
        self.similar_btn = ctk.CTkButton(row_s, text="生成相似", command=self.on_tools_similar, height=32)
        self.similar_btn.grid(row=0, column=1, sticky="ew", padx=(4, 0))

        ctk.CTkLabel(parent, text="③ 红石模板复刻（Phase4）", font=ctk.CTkFont(weight="bold")).grid(
            row=10, column=0, sticky="w", padx=4, pady=(14, 2)
        )
        ctk.CTkLabel(
            parent,
            text="匹配 D9 常用/非常用模板并粘贴原理骨架",
            wraplength=250,
            justify="left",
            text_color=("gray40", "gray70"),
            font=ctk.CTkFont(size=12),
        ).grid(row=11, column=0, sticky="w", padx=4)
        self.redstone_btn = ctk.CTkButton(
            parent, text="红石模板复刻", command=self.on_tools_redstone, height=34
        )
        self.redstone_btn.grid(row=12, column=0, sticky="ew", padx=4, pady=6)

        self.paste_rs_btn = ctk.CTkButton(
            parent,
            text="红石嵌入当前建筑",
            command=self.on_tools_paste_redstone,
            height=34,
        )
        self.paste_rs_btn.grid(row=13, column=0, sticky="ew", padx=4, pady=6)


        ctk.CTkLabel(parent, text="④ 一键流水线", font=ctk.CTkFont(weight="bold")).grid(
            row=14, column=0, sticky="w", padx=4, pady=(14, 2)
        )
        ctk.CTkLabel(
            parent,
            text="分析 → 相似生成 → 红石模板（可选跳过）",
            wraplength=250,
            justify="left",
            text_color=("gray40", "gray70"),
            font=ctk.CTkFont(size=12),
        ).grid(row=15, column=0, sticky="w", padx=4)
        self.pipe_skip_rs = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(parent, text="跳过红石复刻", variable=self.pipe_skip_rs).grid(
            row=16, column=0, sticky="w", padx=4, pady=4
        )
        self.pipeline_btn = ctk.CTkButton(
            parent,
            text="一键流水线",
            command=self.on_tools_pipeline,
            height=40,
            font=ctk.CTkFont(size=14, weight="bold"),
            fg_color=("#1d4e89", "#1d4e89"),
        )
        self.pipeline_btn.grid(row=17, column=0, sticky="ew", padx=4, pady=(8, 4))

        self.tools_log = ctk.CTkTextbox(parent, height=120, wrap="word", font=ctk.CTkFont(size=12))
        self.tools_log.grid(row=17, column=0, sticky="ew", padx=4, pady=(8, 4))
        self.tools_log.insert("1.0", "选择参考文件后点上方按钮。\n报告默认在 outputs/analyze、outputs/pipeline 等。")
        self.tools_log.configure(state="disabled")

        ctk.CTkLabel(parent, text="⑤ 设计方案", font=ctk.CTkFont(weight="bold")).grid(
            row=18, column=0, sticky="w", padx=4, pady=(14, 2)
        )
        ctk.CTkLabel(
            parent,
            text="命名保存 / 再打开 / 手改后写回 / 提交新 litematic",
            wraplength=250,
            justify="left",
            text_color=("gray40", "gray70"),
            font=ctk.CTkFont(size=12),
        ).grid(row=19, column=0, sticky="w", padx=4)
        self.scheme_merge_var = ctk.StringVar(value="overlay")
        ctk.CTkOptionMenu(
            parent,
            variable=self.scheme_merge_var,
            values=["overlay", "replace", "merge"],
            width=200,
        ).grid(row=20, column=0, sticky="ew", padx=4, pady=4)
        row_sch = ctk.CTkFrame(parent, fg_color="transparent")
        row_sch.grid(row=21, column=0, sticky="ew", padx=4, pady=4)
        row_sch.grid_columnconfigure((0, 1), weight=1)
        ctk.CTkButton(row_sch, text="存为方案", command=self.on_scheme_save_as, height=32).grid(
            row=0, column=0, sticky="ew", padx=(0, 4)
        )
        ctk.CTkButton(row_sch, text="打开方案", command=self.on_scheme_open, height=32).grid(
            row=0, column=1, sticky="ew", padx=(4, 0)
        )
        row_sch2 = ctk.CTkFrame(parent, fg_color="transparent")
        row_sch2.grid(row=22, column=0, sticky="ew", padx=4, pady=4)
        row_sch2.grid_columnconfigure((0, 1), weight=1)
        ctk.CTkButton(
            row_sch2, text="保存到方案", command=self.on_scheme_save, height=32
        ).grid(row=0, column=0, sticky="ew", padx=(0, 4))
        ctk.CTkButton(
            row_sch2, text="导出方案", command=self.on_scheme_export, height=32
        ).grid(row=0, column=1, sticky="ew", padx=(4, 0))
        ctk.CTkButton(
            parent,
            text="导入投影到当前方案",
            command=self.on_scheme_import_litematic,
            height=34,
            fg_color=("#6c3483", "#6c3483"),
        ).grid(row=23, column=0, sticky="ew", padx=4, pady=(4, 8))

        ctk.CTkButton(parent, text="打开输出目录", command=self.open_out_dir, height=28).grid(
            row=24, column=0, sticky="ew", padx=4, pady=(4, 4)
        )
        ctk.CTkButton(
            parent, text="打开 schemes 目录", command=self.on_scheme_open_folder, height=28
        ).grid(row=25, column=0, sticky="ew", padx=4, pady=(4, 12))

    def _tools_pick_litematic(self) -> None:
        path = filedialog.askopenfilename(
            title="选择参考 .litematic",
            filetypes=[("Litematic", "*.litematic"), ("全部", "*.*")],
            initialdir=str(self.root_dir / "data"),
        )
        if path:
            self.tools_ref_var.set(path)

    def _tools_ref_path(self) -> Path | None:
        raw = (self.tools_ref_var.get() or "").strip().strip('"')
        if not raw:
            messagebox.showwarning("缺少文件", "请先选择参考 .litematic")
            return None
        path = Path(raw)
        if not path.is_file():
            messagebox.showerror("文件不存在", str(path))
            return None
        return path

    def _tools_append_log(self, text: str) -> None:
        self.tools_log.configure(state="normal")
        self.tools_log.insert("end", text.rstrip() + "\n")
        self.tools_log.see("end")
        self.tools_log.configure(state="disabled")

    def _tools_set_busy(self, busy: bool) -> None:
        self._tools_busy = busy
        state = "disabled" if busy else "normal"
        for btn in (
            self.analyze_btn,
            self.open_report_btn,
            self.ingest_btn,
            self.similar_btn,
            self.redstone_btn,
            self.paste_rs_btn,
            self.pipeline_btn,
        ):
            btn.configure(state=state)

    def _tools_run_py(self, args: list[str], done_msg: str, on_ok=None) -> None:
        if self._tools_busy:
            return
        self._tools_set_busy(True)
        self._set_status("工具运行中…")
        self._tools_append_log("> " + " ".join(args))

        def worker() -> None:
            err: Exception | None = None
            out = ""
            try:
                proc = subprocess.run(
                    [sys.executable, *args],
                    cwd=str(self.root_dir),
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                )
                out = (proc.stdout or "") + ("\n" + proc.stderr if proc.stderr else "")
                if proc.returncode != 0:
                    err = RuntimeError(
                        f"退出码 {proc.returncode}\n{(proc.stderr or proc.stdout or '')[-800:]}"
                    )
            except Exception as exc:  # noqa: BLE001
                err = exc

            def done() -> None:
                self._tools_set_busy(False)
                if out.strip():
                    tail = out.strip()
                    if len(tail) > 1200:
                        tail = "…\n" + tail[-1200:]
                    self._tools_append_log(tail)
                if err is not None:
                    self._set_status(f"工具失败：{err}")
                    messagebox.showerror("工具失败", str(err)[:1500])
                    return
                self._set_status(done_msg)
                self._tools_append_log(done_msg)
                self.refresh_lists()
                if on_ok is not None:
                    on_ok()

            self.after(0, done)

        threading.Thread(target=worker, daemon=True).start()

    def on_tools_analyze(self) -> None:
        path = self._tools_ref_path()
        if path is None:
            return
        out_md = self.root_dir / "outputs" / "analyze" / f"{path.stem}_report.md"

        def after_ok() -> None:
            self._tools_last_report = out_md if out_md.is_file() else None
            if self._tools_last_report:
                self._tools_append_log(f"报告：{self._tools_last_report}")

        self._tools_run_py(
            ["scripts/analyze_litematic.py", str(path), "--write-json"],
            f"分析完成 → {out_md.name}",
            on_ok=after_ok,
        )

    def on_tools_open_report(self) -> None:
        candidates: list[Path] = []
        if self._tools_last_report and self._tools_last_report.is_file():
            candidates.append(self._tools_last_report)
        ref = (self.tools_ref_var.get() or "").strip().strip('"')
        if ref:
            stem = Path(ref).stem
            candidates.append(self.root_dir / "outputs" / "analyze" / f"{stem}_report.md")
            pipe = self.root_dir / "outputs" / "pipeline"
            if pipe.is_dir():
                for d in sorted(pipe.glob(f"{stem}*"), reverse=True):
                    r = d / "pipeline_report.md"
                    if r.is_file():
                        candidates.append(r)
                        break
                    r2 = d / "01_analyze" / f"{stem}_report.md"
                    if r2.is_file():
                        candidates.append(r2)
                        break
        for c in candidates:
            if c.is_file():
                try:
                    os.startfile(str(c))  # type: ignore[attr-defined]
                except AttributeError:
                    subprocess.Popen(["xdg-open", str(c)])
                self._set_status(f"已打开 {c.name}")
                return
        messagebox.showinfo("无报告", "请先运行「分析」或「一键流水线」。")

    def on_tools_ingest(self) -> None:
        path = self._tools_ref_path()
        if path is None:
            return
        self._tools_run_py(
            ["scripts/learn_from_reference.py", "ingest", str(path)],
            "特征已入库（data/feature_index）",
        )

    def on_tools_similar(self) -> None:
        path = self._tools_ref_path()
        if path is None:
            return
        num = int(round(self.tools_sim_num.get()))
        out_dir = self.root_dir / "outputs" / "similar_gui"
        self._tools_run_py(
            [
                "scripts/learn_from_reference.py",
                "similar",
                "--litematic",
                str(path),
                "--num",
                str(num),
                "--out-dir",
                str(out_dir),
            ],
            f"相似变体已写入 {out_dir}",
            on_ok=lambda: self._tools_try_load_latest(out_dir),
        )

    def on_tools_redstone(self) -> None:
        path = self._tools_ref_path()
        if path is None:
            return
        out_dir = self.root_dir / "outputs" / "redstone_replicate_gui"
        self._tools_run_py(
            [
                "scripts/replicate_redstone.py",
                "replicate",
                str(path),
                "--out-dir",
                str(out_dir),
            ],
            f"红石复刻完成 → {out_dir}",
            on_ok=lambda: self._tools_try_load_latest(out_dir),
        )


    def on_tools_paste_redstone(self) -> None:
        """Paste a redstone template into the currently loaded design npz."""
        if self.current_voxels is None or self.current_path is None:
            messagebox.showinfo("提示", "请先在「浏览」打开一个建筑 .npz")
            return
        path = Path(self.current_path)
        if path.suffix.lower() not in (".npz", ".npy") and not path.name.endswith(".npz.npz"):
            messagebox.showinfo("提示", "当前文件不是建筑 npz，请先打开 sample_*.npz")
            return
        out_dir = self.root_dir / "outputs" / "design" / "rs_paste_gui"
        self._tools_run_py(
            [
                "scripts/paste_redstone_into_design.py",
                "--npz",
                str(path),
                "--template",
                "auto:door",
                "--out-dir",
                str(out_dir),
                "--companion",
                "--companion-name",
                "欧式_红石门控",
            ],
            f"红石嵌入完成 → {out_dir}",
            on_ok=lambda: self._tools_try_load_latest(out_dir),
        )

    def on_tools_pipeline(self) -> None:
        path = self._tools_ref_path()
        if path is None:
            return
        num = int(round(self.tools_sim_num.get()))
        args = [
            "scripts/pipeline_from_reference.py",
            str(path),
            "--num",
            str(num),
        ]
        if self.pipe_skip_rs.get():
            args.append("--skip-redstone")
        out_root = self.root_dir / "outputs" / "pipeline"

        def after_ok() -> None:
            stem = path.stem
            if out_root.is_dir():
                matches = sorted(
                    out_root.glob(f"{stem}*"),
                    key=lambda x: x.stat().st_mtime,
                    reverse=True,
                )
                if matches:
                    best = matches[0]
                    report = best / "pipeline_report.md"
                    if report.is_file():
                        self._tools_last_report = report
                    self._tools_try_load_latest(best)

        self._tools_run_py(args, "一键流水线完成", on_ok=after_ok)

    def _tools_try_load_latest(self, folder: Path) -> None:
        if not folder.is_dir():
            return
        npzs = sorted(folder.rglob("*.npz"), key=lambda x: x.stat().st_mtime, reverse=True)
        if not npzs:
            lites = sorted(
                folder.rglob("*.litematic"), key=lambda x: x.stat().st_mtime, reverse=True
            )
            if lites:
                self._tools_append_log(f"产出：{lites[0]}")
            return
        target = npzs[0]
        try:
            self.refresh_lists()
            self._switch_mode(MODE_BROWSE)
            if target.parent == self.out_dir or self.out_dir in target.parents:
                self.sample_var.set(target.name)
            self.load_and_show(target)
            self._tools_append_log(f"已预览 {target.name}")
        except Exception as exc:  # noqa: BLE001
            self._tools_append_log(f"预览跳过：{exc}")


    def _rel_out_dir(self) -> str:
        try:
            return str(self.out_dir.resolve().relative_to(self.root_dir.resolve()))
        except ValueError:
            return str(self.out_dir)

    def _update_out_dir_label(self) -> None:
        if hasattr(self, "out_dir_label"):
            self.out_dir_label.configure(text=self._rel_out_dir())

    def refresh_batch_menu(self) -> None:
        """Rebuild sample-directory dropdown (samples + recent design/*/npz)."""
        pairs = discover_sample_dirs(self.root_dir)
        self._batch_label_to_path = {label: path for label, path in pairs}
        # Ensure current out_dir is representable even if custom-picked
        cur = self.out_dir.resolve()
        match_label = None
        for label, path in pairs:
            if path.resolve() == cur:
                match_label = label
                break
        if match_label is None:
            n = _count_listable_samples(self.out_dir)
            match_label = f"当前目录 ({n})"
            self._batch_label_to_path[match_label] = cur
            pairs = [(match_label, cur)] + pairs
        labels = [p[0] for p in pairs] or ["(无)"]
        if hasattr(self, "batch_menu"):
            self.batch_menu.configure(values=labels)
            self.batch_var.set(match_label if match_label in labels else labels[0])
        self._update_out_dir_label()

    def on_batch_selected(self, label: str) -> None:
        if not label or label == "(无)":
            return
        path = self._batch_label_to_path.get(label)
        if path is None:
            return
        self.set_out_dir(path, autoload=True)

    def pick_sample_dir(self) -> None:
        initial = str(self.out_dir if self.out_dir.is_dir() else self.root_dir / "outputs")
        chosen = filedialog.askdirectory(title="选择样本目录（含 sample_*.npz）", initialdir=initial)
        if not chosen:
            return
        self.set_out_dir(Path(chosen), autoload=True)

    def set_out_dir(self, path: Path | str, *, autoload: bool = False) -> None:
        """Switch browse sample folder; keeps Generate/Design/Edit modes intact."""
        new_dir = Path(path)
        if not new_dir.is_absolute():
            new_dir = self.root_dir / new_dir
        if self._dirty:
            if not messagebox.askyesno("未保存", "当前有未保存的修改，切换目录将丢弃修改。继续？"):
                self.refresh_batch_menu()
                return
            self._dirty = False
        self.out_dir = new_dir
        self.refresh_batch_menu()
        self.refresh_lists()
        self._set_status(f"样本目录：{self._rel_out_dir()}")
        if autoload:
            self._autoload_first_sample()

    def open_out_dir(self) -> None:
        self.out_dir.mkdir(parents=True, exist_ok=True)
        path = str(self.out_dir)
        try:
            os.startfile(path)  # type: ignore[attr-defined]
        except AttributeError:
            subprocess.Popen(["xdg-open", path])



    def _refresh_scheme_label(self) -> None:
        if not hasattr(self, "scheme_label"):
            return
        if self._scheme_slug:
            self.scheme_label.configure(text=f"当前方案：{self._scheme_slug}")
        else:
            self.scheme_label.configure(text="当前方案：未绑定")

    def _bind_scheme(
        self, slug: str, voxels, npz_path: Path, *, switch_edit: bool = False
    ) -> None:
        self._scheme_slug = slug
        self.current_voxels = voxels
        self.current_path = Path(npz_path)
        self._undo_stack.clear()
        self._dirty = False
        if hasattr(self, "undo_btn"):
            self._refresh_undo_redo_buttons()
        self._refresh_scheme_label()
        self._refresh_steps()
        self._update_info_panel()
        self._rebuild_block_list()
        self.render_voxels(voxels)
        non_air = int((voxels > 0).sum())
        self._set_status(f"已打开方案 {slug}，non_air={non_air}。")
        try:
            self._refresh_scheme_list()
        except Exception:
            pass
        if switch_edit:
            self._switch_mode(MODE_EDIT)

    def on_scheme_save_as(self) -> None:
        if self.current_voxels is None:
            messagebox.showwarning("无数据", "请先加载或生成建筑")
            return
        name = simpledialog.askstring("存为方案", "方案名称（例如：庄园）:", parent=self)
        if not name or not name.strip():
            return
        style = "medieval"
        terrain = "flat"
        if hasattr(self, "style_var"):
            style = self.style_var.get() or style
        if hasattr(self, "terrain_var"):
            terrain = self.terrain_var.get() or terrain
        try:
            result = create_scheme(
                name.strip(),
                voxels=self.current_voxels,
                style=style,
                terrain=terrain,
                notes="",
            )
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror("存为方案失败", str(exc))
            return
        slug = result["slug"]
        self._bind_scheme(slug, self.current_voxels, result["dir"] / "current.npz")
        self._refresh_scheme_list()
        messagebox.showinfo(
            "已保存方案",
            f"名称：{name.strip()}\nslug：{slug}\n目录：{result['dir']}\n非空气：{result['non_air']}",
        )

    def on_scheme_save(self) -> None:
        if self.current_voxels is None:
            messagebox.showwarning("无数据", "请先加载或生成建筑")
            return
        slug = self._scheme_slug
        if not slug:
            self.on_scheme_save_as()
            return
        try:
            result = save_scheme(slug, self.current_voxels, bump_version=True)
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror("保存失败", str(exc))
            return
        self.current_path = Path(result["npz"])
        self._dirty = False
        self._refresh_scheme_label()
        self._update_info_panel()
        self._set_status(f"已写回方案 {slug}（non_air={result['non_air']}，已留 history/版本）")

    def on_scheme_open(self) -> None:
        rows = list_schemes()
        if not rows:
            messagebox.showinfo("无方案", "还没有方案。先「存为方案」或用 scripts/scheme.py create。")
            return
        labels = [f"{r.get('slug')}  |  {r.get('name')}  |  non_air={r.get('non_air')}" for r in rows]
        # simple pick dialog via OptionMenu popup
        pick = {"value": labels[0]}

        win = ctk.CTkToplevel(self)
        win.title("打开方案")
        win.geometry("520x160")
        win.transient(self)
        win.grab_set()
        var = ctk.StringVar(value=labels[0])
        ctk.CTkLabel(win, text="选择方案：").pack(anchor="w", padx=12, pady=(12, 4))
        ctk.CTkOptionMenu(win, variable=var, values=labels, width=480).pack(padx=12, pady=4)

        def ok() -> None:
            pick["value"] = var.get()
            win.destroy()

        ctk.CTkButton(win, text="打开", command=ok).pack(pady=12)
        self.wait_window(win)
        chosen = pick.get("value") or ""
        if not chosen:
            return
        slug = chosen.split("|", 1)[0].strip()
        if self._dirty:
            if not messagebox.askyesno("未保存", "当前有未保存修改，打开方案将丢弃。继续？"):
                return
        try:
            data = load_scheme(slug)
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror("打开失败", str(exc))
            return
        self._bind_scheme(slug, data["voxels"], data["npz_path"], switch_edit=True)

    def on_scheme_export(self) -> None:
        slug = self._scheme_slug
        if not slug:
            if self.current_voxels is None:
                messagebox.showwarning("无方案", "请先打开或另为方案")
                return
            # export current voxels via normal export path
            self.on_export_litematic()
            return
        try:
            # Bound export reads current.npz from disk — flush dirty GUI edits first
            # so "导出方案" matches what the user sees.
            if self._dirty and self.current_voxels is not None:
                saved = save_scheme(slug, self.current_voxels)
                self.current_path = Path(saved["npz"])
                self._dirty = False
                self._refresh_scheme_label()
            ver_label = self.export_version_var.get() if hasattr(self, "export_version_var") else None
            ver_id = version_id_from_menu_label(ver_label) if ver_label else None
            info = export_scheme_litematic(slug, target_version=ver_id)
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror("导出失败", str(exc))
            return
        lit_path = info.get("path") or info.get("out_path")
        bom_note = ""
        if lit_path and self.current_voxels is not None:
            bom_info = self._write_export_bom(
                self.current_voxels,
                lit_path,
                source=f"scheme:{slug}",
                extra={"slug": slug, "litematic": str(lit_path)},
            )
            if bom_info.get("error"):
                bom_note = f"\n材料清单失败：{bom_info['error']}"
            elif not bom_info.get("skipped"):
                md = (bom_info.get("bom_paths") or {}).get("md", "")
                bom_note = f"\n材料清单：{md}"
        messagebox.showinfo(
            "方案已导出",
            f"slug：{slug}\n文件：{lit_path or info}{bom_note}",
        )



    def on_scheme_import_litematic(self) -> None:
        slug = self._scheme_slug
        if not slug:
            messagebox.showwarning("未绑定方案", "请先「打开方案」或「存为方案」")
            return
        path = filedialog.askopenfilename(
            title="选择要导入到方案的 .litematic",
            filetypes=[("Litematic", "*.litematic"), ("全部", "*.*")],
            initialdir=str(self.root_dir / "data"),
        )
        if not path:
            return
        mode = "overlay"
        if hasattr(self, "scheme_merge_var"):
            mode = self.scheme_merge_var.get() or "overlay"
        try:
            result = scheme_import_litematic(slug, path, mode=mode)  # type: ignore[arg-type]
            data = load_scheme(slug)
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror("导入失败", str(exc))
            return
        self._bind_scheme(slug, data["voxels"], data["npz_path"], switch_edit=True)
        messagebox.showinfo(
            "已导入投影",
            f"方案：{slug}\n模式：{mode}\n非空气：{result['non_air']}\nref：{result['ref'].name}",
        )

    def on_scheme_open_folder(self) -> None:
        d = schemes_root()
        d.mkdir(parents=True, exist_ok=True)
        try:
            if sys.platform.startswith("win"):
                os.startfile(str(d))  # type: ignore[attr-defined]
            else:
                subprocess.Popen(["xdg-open", str(d)])
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror("无法打开", str(exc))




    def _refresh_scheme_list(self) -> None:
        """Populate browse-side scheme list (UX P2)."""
        frame = getattr(self, "scheme_list_frame", None)
        if frame is None:
            return
        for child in frame.winfo_children():
            child.destroy()
        self._scheme_list_rows = []
        try:
            rows = list_schemes()
        except Exception as exc:  # noqa: BLE001
            ctk.CTkLabel(frame, text=f"读取失败：{exc}", wraplength=250, anchor="w").pack(
                fill="x", padx=2, pady=2
            )
            return
        if not rows:
            ctk.CTkLabel(
                frame,
                text="暂无方案。点「新建」或「另存」创建。",
                wraplength=250,
                anchor="w",
                text_color=("gray40", "gray70"),
            ).pack(fill="x", padx=2, pady=4)
            return
        for r in rows:
            slug = str(r.get("slug") or "")
            name = str(r.get("name") or slug)
            non_air = r.get("non_air", "?")
            updated = str(r.get("updated") or "")[:16]
            label = f"{name}\n{slug} · 块{non_air} · {updated}"
            selected = slug == self._scheme_slug
            btn = ctk.CTkButton(
                frame,
                text=label,
                anchor="w",
                height=44,
                fg_color=("#1f538d", "#14375e") if selected else ("gray75", "gray30"),
                command=lambda s=slug: self._open_scheme_slug(s),
            )
            btn.pack(fill="x", padx=2, pady=2)
            self._scheme_list_rows.append((slug, btn))

    def _open_scheme_slug(self, slug: str) -> None:
        if self._dirty:
            if not messagebox.askyesno("未保存", "当前有未保存修改，打开方案会丢弃它们。继续？"):
                return
        try:
            data = load_scheme(slug)
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror("打开失败", str(exc))
            return
        self._bind_scheme(slug, data["voxels"], data["npz_path"], switch_edit=True)

    def on_scheme_new(self) -> None:
        """Create empty scheme or from current voxels."""
        name = simpledialog.askstring("新建方案", "方案名称（中文可）：", parent=self)
        if not name or not name.strip():
            return
        style = self.style_var.get() if hasattr(self, "style_var") else "medieval"
        terrain = self.terrain_var.get() if hasattr(self, "terrain_var") else "flat"
        use_current = False
        if self.current_voxels is not None:
            use_current = messagebox.askyesno(
                "新建方案",
                "是否把当前预览体素写入新方案？\n选「否」则创建空方案。",
            )
        try:
            result = create_scheme(
                name.strip(),
                voxels=self.current_voxels if use_current else None,
                style=style,
                terrain=terrain,
                notes="",
            )
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror("新建失败", str(exc))
            return
        data = load_scheme(result["slug"])
        self._bind_scheme(result["slug"], data["voxels"], data["npz_path"], switch_edit=True)
        self._refresh_scheme_list()
        self._flash_toast(f"已新建方案 {name.strip()}")

    def on_scheme_import_npz(self) -> None:
        """Import an npz into a new scheme."""
        path = filedialog.askopenfilename(
            title="选择要导入的 .npz",
            filetypes=[("NPZ", "*.npz"), ("全部", "*.*")],
            initialdir=str(self.out_dir),
        )
        if not path:
            return
        name = simpledialog.askstring(
            "导入为方案",
            "方案名称：",
            initialvalue=Path(path).stem,
            parent=self,
        )
        if not name or not name.strip():
            return
        style = self.style_var.get() if hasattr(self, "style_var") else "medieval"
        terrain = self.terrain_var.get() if hasattr(self, "terrain_var") else "flat"
        try:
            result = create_scheme(
                name.strip(),
                from_npz=path,
                style=style,
                terrain=terrain,
            )
            data = load_scheme(result["slug"])
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror("导入失败", str(exc))
            return
        self._bind_scheme(result["slug"], data["voxels"], data["npz_path"], switch_edit=True)
        self._refresh_scheme_list()
        self._flash_toast(f"已导入 {name.strip()}")

    def on_export_to_game(self) -> None:
        """One-click: write .litematic to PCL schematics + BOM + toast. UX P2."""
        if self.current_voxels is None:
            self._set_status("没有可导出的体素，请先加载或生成建筑")
            messagebox.showwarning("进游戏", "请先加载样本 / 打开方案 / 生成建筑")
            return
        base = "ai_preview"
        if self._scheme_slug:
            if self._dirty:
                try:
                    saved = save_scheme(self._scheme_slug, self.current_voxels)
                    self.current_path = Path(saved["npz"])
                    self._dirty = False
                except Exception as exc:  # noqa: BLE001
                    messagebox.showerror("保存方案失败", str(exc))
                    return
            base = self._scheme_slug
        elif self.current_path is not None:
            stem = self.current_path.stem
            if stem.endswith(".npz"):
                stem = Path(stem).stem
            base = f"ai_{stem}"
        label = ""
        if hasattr(self, "export_version_var"):
            label = self.export_version_var.get()
        target = version_id_from_menu_label(label) if label else DEFAULT_VERSION_ID
        try:
            ver = get_version(target)
            info = export_voxels_to_companion(
                self.current_voxels,
                self.palette,
                name=base,
                target_version=target,
            )
        except Exception as exc:  # noqa: BLE001
            self._set_status(f"进游戏导出失败：{exc}")
            messagebox.showerror("进游戏失败", str(exc))
            return
        path = Path(info["path"])
        schematics_dir = info.get("schematics_dir") or str(resolve_schematics_dir())
        bom_info = self._write_export_bom(
            self.current_voxels,
            path,
            source=f"scheme:{self._scheme_slug}" if self._scheme_slug else str(self.current_path or base),
            extra={
                "litematic": str(path),
                "target_version": info.get("target_version"),
                "slug": self._scheme_slug,
            },
        )
        bom_line = ""
        if bom_info.get("error"):
            bom_line = f"材料清单失败：{bom_info['error']}"
        elif not bom_info.get("skipped"):
            md = (bom_info.get("bom_paths") or {}).get("md", "")
            totals = bom_info.get("totals") or {}
            bom_line = (
                f"材料清单：{md}（种类 {totals.get('unique_blocks', '?')} / "
                f"合计 {totals.get('total_blocks', '?')}）"
            )
        tip = "游戏里 Andy：列出投影 → 建造"
        msg = (
            f"已进游戏目录\n{path}\n\n"
            f"目标版本：{info.get('target_display', ver.display_name)}\n"
            f"目录：{schematics_dir}\n"
            f"{bom_line}\n\n"
            f"提示：{tip}"
        )
        status = f"已导出 {path} · {tip}"
        if bom_line:
            status += f" · {bom_line[:80]}"
        self._set_status(status)
        self._flash_toast(f"已写入 PCL · {path.name}", ms=1600)
        messagebox.showinfo("进游戏成功", msg)
        # UX P3: sidecar + step card + clipboard + refresh list
        self._last_export_name = path.name
        self._bridge_selected = str(path)
        try:
            write_last_export_sidecar(
                Path(schematics_dir),
                litematic_path=path,
                slug=self._scheme_slug,
                extra={
                    "target_version": info.get("target_version"),
                    "bom": bom_info if isinstance(bom_info, dict) else {},
                },
            )
        except Exception as _sc_exc:  # noqa: BLE001
            self._set_status(f"已导出；LAST_EXPORT 写入失败：{_sc_exc}")
        try:
            copy_text_to_clipboard(path.name, root_widget=self)
        except Exception:
            pass
        try:
            self._refresh_game_bridge()
        except Exception:
            pass
        self._show_build_step_card(path.name, schematics_dir)

        open_folder = bool(getattr(self, "open_folder_var", None) and self.open_folder_var.get())
        if open_folder:
            try:
                folder = str(Path(schematics_dir))
                if sys.platform.startswith("win"):
                    os.startfile(folder)  # type: ignore[attr-defined]
                else:
                    subprocess.Popen(["xdg-open", folder])
            except Exception as exc:  # noqa: BLE001
                self._set_status(f"已导出，但打开文件夹失败：{exc}")


    # ---- UX P3 game bridge methods ----
    def _schematics_dir_safe(self):
        try:
            return resolve_schematics_dir(create=False)
        except Exception:
            try:
                return resolve_schematics_dir(create=True)
            except Exception:
                return None

    def _refresh_game_bridge(self) -> None:
        """Refresh PCL schematics list + MC process status."""
        frame = getattr(self, "bridge_list_frame", None)
        status = getattr(self, "bridge_status_label", None)
        d = self._schematics_dir_safe()
        det = detect_minecraft_running()
        path_note = str(d) if d is not None else "(目录不可用)"
        exists = bool(d is not None and Path(d).is_dir())
        if status is not None:
            st = det.get("label_zh") or ""
            miss = "" if exists else " · schematics 目录缺失"
            status.configure(text=f"{st}{miss}\n{path_note}")
        if frame is None:
            return
        for child in frame.winfo_children():
            child.destroy()
        self._bridge_rows = []
        if d is None or not Path(d).is_dir():
            ctk.CTkLabel(
                frame,
                text="找不到 schematics 目录（检查 mc-companion .env SCHEMATICS_DIR）",
                wraplength=260,
                anchor="w",
                text_color=("gray40", "gray70"),
            ).pack(fill="x", padx=2, pady=4)
            return
        rows = list_schematics(Path(d))
        if not rows:
            ctk.CTkLabel(
                frame,
                text="目录为空：用「进游戏」导出后会出现在这里",
                wraplength=260,
                anchor="w",
                text_color=("gray40", "gray70"),
            ).pack(fill="x", padx=2, pady=4)
            return
        for r in rows[:40]:
            name = r["name"]
            owned = bool(r.get("app_owned"))
            selected = self._bridge_selected and Path(self._bridge_selected).name == name
            mark = "★ " if owned else "· "
            from datetime import datetime as _dt

            try:
                tstr = _dt.fromtimestamp(r["mtime"]).strftime("%m-%d %H:%M")
            except Exception:
                tstr = ""
            label = f"{mark}{name}\n{tstr}"
            fg = ("#1b7f4a", "#146038") if selected else (
                ("#3d6b9a", "#2a4a6a") if owned else ("gray75", "gray30")
            )
            btn = ctk.CTkButton(
                frame,
                text=label,
                anchor="w",
                height=40,
                fg_color=fg,
                command=lambda p=r["path"], n=name: self._select_bridge_item(p, n),
            )
            btn.pack(fill="x", padx=2, pady=1)
            self._bridge_rows.append((r["path"], btn))

    def _select_bridge_item(self, path: str, name: str) -> None:
        self._bridge_selected = path
        self._last_export_name = name
        self._refresh_game_bridge()
        self._flash_toast(f"已选 {name}", ms=700)

    def _schedule_bridge_auto(self) -> None:
        if self._bridge_auto_job is not None:
            try:
                self.after_cancel(self._bridge_auto_job)
            except Exception:
                pass
            self._bridge_auto_job = None
        if not bool(getattr(self, "bridge_auto_var", None) and self.bridge_auto_var.get()):
            return

        def _tick():
            self._bridge_auto_job = None
            try:
                if self.winfo_exists() and bool(self.bridge_auto_var.get()):
                    self._refresh_game_bridge()
            except Exception:
                pass
            try:
                if self.winfo_exists() and bool(self.bridge_auto_var.get()):
                    self._bridge_auto_job = self.after(self._bridge_auto_ms, _tick)
            except Exception:
                pass

        self._bridge_auto_job = self.after(self._bridge_auto_ms, _tick)

    def _on_bridge_auto_toggle(self) -> None:
        self._schedule_bridge_auto()
        if self.bridge_auto_var.get():
            self._refresh_game_bridge()

    def on_open_schematics_folder(self) -> None:
        d = self._schematics_dir_safe()
        if d is None or not Path(d).is_dir():
            messagebox.showwarning("打开目录", "schematics 目录不存在或无法解析。")
            return
        try:
            open_in_explorer(Path(d), select_file=False)
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror("打开目录失败", str(exc))

    def on_reveal_selected_litematic(self) -> None:
        path = self._bridge_selected
        if not path:
            d = self._schematics_dir_safe()
            if d and self._last_export_name:
                cand = Path(d) / self._last_export_name
                path = str(cand) if cand.is_file() else None
        if not path or not Path(path).is_file():
            messagebox.showwarning("定位文件", "请先在列表中点选一个 .litematic")
            return
        try:
            open_in_explorer(Path(path), select_file=True)
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror("定位失败", str(exc))

    def on_copy_export_name(self) -> None:
        name = self._last_export_name
        if not name and self._bridge_selected:
            name = Path(self._bridge_selected).name
        if not name:
            messagebox.showwarning("复制文件名", "还没有导出或选中的投影文件名。")
            return
        ok = copy_text_to_clipboard(name, root_widget=self)
        if ok:
            self._flash_toast(f"已复制 {name}", ms=900)
            self._set_status(f"已复制文件名到剪贴板：{name}")
        else:
            messagebox.showwarning("复制失败", f"无法写入剪贴板。文件名：{name}")

    def on_show_build_steps(self) -> None:
        name = self._last_export_name
        if not name and self._bridge_selected:
            name = Path(self._bridge_selected).name
        d = self._schematics_dir_safe()
        if not name:
            messagebox.showinfo(
                "建造步骤",
                "先点「进游戏」导出，或在投影列表中选中文件后再看步骤卡。",
            )
            return
        self._show_build_step_card(name, str(d) if d else "(未知目录)")

    def _show_build_step_card(self, filename: str, schematics_dir) -> None:
        card = build_step_card_text(filename=filename, schematics_dir=schematics_dir)
        messagebox.showinfo("建造步骤卡", card)


    def _bind_canvas_interactions(self) -> None:
        """Orbit LOD on drag; click-to-edit when not dragging (MCBlock-like)."""
        self.canvas.mpl_connect("button_press_event", self._on_canvas_press)
        self.canvas.mpl_connect("button_release_event", self._on_canvas_release)
        self.canvas.mpl_connect("motion_notify_event", self._on_canvas_motion)
        widget = self.canvas.get_tk_widget()
        widget.bind("<Key>", self._on_canvas_key)
        widget.bind("<Control-z>", lambda e: (self.on_undo(), "break")[1])
        widget.bind("<Control-y>", lambda e: (self.on_redo(), "break")[1])
        widget.bind("<Control-Z>", lambda e: (self.on_undo(), "break")[1])
        widget.bind("<Control-c>", lambda e: (self.on_copy_selection(), "break")[1])
        widget.bind("<Control-x>", lambda e: (self.on_cut_selection(), "break")[1])
        widget.bind("<Control-v>", lambda e: (self.on_paste_at_selection(), "break")[1])
        self.bind("<Control-z>", lambda e: self.on_undo())
        self.bind("<Control-y>", lambda e: self.on_redo())
        for d in range(1, 10):
            self.bind(str(d), lambda e, n=d: self._select_hotbar(n - 1))
            widget.bind(str(d), lambda e, n=d: self._select_hotbar(n - 1))
        try:
            widget.focus_set()
        except Exception:
            pass


    def _push_undo(self) -> None:
        """Snapshot current voxels before a mutating edit."""
        if self.current_voxels is None:
            return
        self._undo_stack.push(self.current_voxels)

    def _refresh_undo_redo_buttons(self) -> None:
        if hasattr(self, "undo_btn"):
            self.undo_btn.configure(
                state=("normal" if self._undo_stack.can_undo() else "disabled")
            )
        if hasattr(self, "redo_btn"):
            self.redo_btn.configure(
                state=("normal" if self._undo_stack.can_redo() else "disabled")
            )

    def _refresh_clip_label(self) -> None:
        if not hasattr(self, "clip_label"):
            return
        if self._clipboard.empty():
            self.clip_label.configure(text="剪贴板：空")
        else:
            sx, sy, sz = self._clipboard.size or (0, 0, 0)
            self.clip_label.configure(
                text=f"剪贴板：{sx}×{sy}×{sz} ({self._clipboard.non_air})"
            )

    def _on_brush_change(self, value: str) -> None:
        self._brush_radius = int(BRUSH_PRESETS.get(value, 0))
        self._set_status(f"笔刷：{value}（半径 {self._brush_radius}）")

    def _on_box_fill_toggle(self) -> None:
        self._box_anchor = None
        on = bool(self.box_fill_var.get()) if hasattr(self, "box_fill_var") else False
        self._set_status("盒填：开 — 点两次对角" if on else "盒填：关 — 用笔刷半径")

    def _after_voxel_edit(self, msg: str) -> None:
        self._update_workbench_hint()
        self._update_region_sel_label()
        self._dirty = True
        self._refresh_undo_redo_buttons()
        self._rebuild_block_list()
        self._refresh_steps()
        self._update_info_panel()
        if hasattr(self, "sel_pos_label") and self._sel_pos is not None:
            extra = f" → {self._sel_corner_b}" if self._sel_corner_b is not None else ""
            self.sel_pos_label.configure(text=f"选中：{self._sel_pos}{extra}")
        if self.current_voxels is not None:
            self.render_voxels(self.current_voxels)
        self._flash_toast(msg)

    def on_copy_selection(self) -> None:
        if self.current_voxels is None or self._sel_pos is None:
            self._set_status("请先用「选择」点选（或选两角）")
            return
        self._clipboard = copy_region(self.current_voxels, self._sel_pos, self._sel_corner_b)
        self._refresh_clip_label()
        if self._clipboard.empty():
            self._set_status("复制失败：区域为空")
            return
        self._set_status(
            f"已复制 {self._clipboard.size}，non_air={self._clipboard.non_air}"
        )

    def on_cut_selection(self) -> None:
        if self.current_voxels is None or self._sel_pos is None:
            self._set_status("请先用「选择」点选（或选两角）")
            return
        self._push_undo()
        self._clipboard = cut_region(self.current_voxels, self._sel_pos, self._sel_corner_b)
        if self._clipboard.empty():
            self._undo_stack._undo.pop()
            self._set_status("剪切失败：区域为空")
            return
        self._sel_pos = None
        self._sel_corner_b = None
        self._refresh_clip_label()
        self._after_voxel_edit(
            f"已剪切 {self._clipboard.size}，non_air={self._clipboard.non_air}"
        )

    def on_paste_at_selection(self) -> None:
        if self.current_voxels is None:
            self._set_status("请先加载建筑")
            return
        if self._clipboard.empty():
            self._set_status("剪贴板为空，请先复制/剪切")
            return
        dest = self._sel_pos
        if dest is None:
            self._set_status("请先选择粘贴角点（选择工具点一下）")
            return
        self._push_undo()
        n = paste_region(self.current_voxels, self._clipboard, dest, mode="overlay")
        if n == 0:
            self._undo_stack._undo.pop()
            self._set_status("粘贴无变化（越界或全空）")
            return
        self._after_voxel_edit(f"已粘贴 {n} 格到 {dest}")

    def _on_voxel_tool_change(self, value: str) -> None:
        mapping = {
            "选择": TOOL_SELECT,
            "破坏": TOOL_BREAK,
            "放置": TOOL_PLACE,
            "涂改": TOOL_PAINT,
            "移动": TOOL_MOVE,
        }
        self._voxel_tool = mapping.get(value, TOOL_SELECT)
        self._move_src = None
        self._update_workbench_hint()
        self._set_status(f"工具：{value}（左键）· 右键放置 · 栏{self._hotbar_slot + 1}")

    def _on_canvas_press(self, event) -> None:
        if event.inaxes != self.ax:
            return
        if event.button not in (1, 3):
            return
        self._press_button = int(event.button)
        self._press_xy = (float(event.x), float(event.y))
        self._did_drag = False

    def _on_canvas_motion(self, event) -> None:
        if self._press_xy is None:
            return
        dx = float(event.x) - self._press_xy[0]
        dy = float(event.y) - self._press_xy[1]
        if (dx * dx + dy * dy) < 36:
            return
        self._did_drag = True
        # Orbit LOD only on left-button drag; right-drag just cancels click-place
        if self._press_button != 1:
            return
        if not self._orbiting:
            self._orbiting = True
            self._orbit_lod_active = True
            if self.current_voxels is not None:
                self.render_voxels(self.current_voxels, orbit_lod=True)

    def _on_canvas_release(self, event) -> None:
        btn = int(getattr(event, "button", 0) or 0)
        press_btn = self._press_button
        self._press_button = None
        press = self._press_xy
        self._press_xy = None

        # Right-click: place from hotbar (Edit, no drag)
        if btn == 3 or press_btn == 3:
            dragged = self._did_drag
            self._did_drag = False
            if self._mode != MODE_EDIT or dragged:
                return
            if event.inaxes != self.ax or press is None:
                return
            # ensure hotbar target is active
            if hasattr(self, "_hotbar_names"):
                self._set_target(self._hotbar_names[self._hotbar_slot])
            self._handle_voxel_click(event, force_tool=TOOL_PLACE)
            return

        if btn != 1:
            return
        was_orbit = self._orbiting
        self._orbiting = False
        if was_orbit or self._did_drag:
            self._orbit_lod_active = False
            if self.current_voxels is not None:
                self.render_voxels(self.current_voxels, orbit_lod=False)
            self._did_drag = False
            return
        self._did_drag = False
        # Click (no drag): voxel tool in EDIT mode
        if self._mode != MODE_EDIT:
            return
        if event.inaxes != self.ax or press is None:
            return
        self._handle_voxel_click(event)

    def _handle_voxel_click(self, event, *, force_tool: str | None = None) -> None:
        if self.current_voxels is None:
            return
        if not self._face_meta:
            self.render_voxels(self.current_voxels, orbit_lod=False)
        meta = pick_nearest_face(self.ax, (float(event.x), float(event.y)), self._face_meta)
        if meta is None:
            self._set_status("未点到外壳面，换个角度再点")
            return
        tool = force_tool or self._voxel_tool
        pos = meta["voxel"]
        box_on = bool(self.box_fill_var.get()) if hasattr(self, "box_fill_var") else False

        if tool == TOOL_SELECT:
            # First click = corner A; Shift/second click = corner B for copy region
            if self._sel_pos is not None and self._sel_corner_b is None and pos != self._sel_pos:
                self._sel_corner_b = pos
            else:
                self._sel_pos = pos
                self._sel_corner_b = None
            bid = int(meta["bid"])
            raw = self.palette.get(bid, str(bid))
            name = short_block_name(raw)
            try:
                zh = block_zh_name(raw)
            except Exception:
                zh = name
            extra = f" → {self._sel_corner_b}" if self._sel_corner_b else ""
            self.sel_pos_label.configure(text=f"选中：{self._sel_pos}{extra} · {zh}")
            self._update_region_sel_label()
            self._select_source(bid, raw)
            self.render_voxels(self.current_voxels)
            self._set_status(f"选中 {self._sel_pos}{extra}（{zh} / {name}）")

        if tool == TOOL_BREAK:
            changed_n = apply_break_brush(self.current_voxels, pos, r, shape=shape)
            msg = f"破坏 {pos} ×{changed_n}" if changed_n else "此处无可破坏"
            if changed_n:
                self._sel_pos = None
        elif tool == TOOL_PLACE:
            tid = self._parse_target_id()
            if tid is None:
                self._undo_stack._undo.pop()
                self._set_status("放置前请先选目标方块")
                return
            dst = place_pos_from_face(meta)
            changed_n = apply_place_brush(self.current_voxels, dst, tid, r, shape=shape)
            msg = f"放置 {dst} ×{changed_n}" if changed_n else f"无法放置到 {dst}（越界或已被占）"
            if changed_n:
                self._sel_pos = dst
        elif tool == TOOL_PAINT:
            tid = self._parse_target_id()
            if tid is None:
                self._undo_stack._undo.pop()
                self._set_status("涂改前请先选目标方块")
                return
            changed_n = apply_paint_brush(self.current_voxels, pos, tid, r, shape=shape)
            msg = f"涂改 {pos} ×{changed_n}" if changed_n else "涂改无变化"
            if changed_n:
                self._sel_pos = pos
        elif tool == TOOL_MOVE:
            self._undo_stack._undo.pop()  # move uses its own push timing
            if self._move_src is None:
                self._move_src = pos
                self._sel_pos = pos
                self.sel_pos_label.configure(text=f"移动：已抓取 {pos}，再点目标外壳面")
                self.render_voxels(self.current_voxels)
                self._set_status(f"已抓取 {pos}，再点目标位置")
                return
            dst = place_pos_from_face(meta)
            self._push_undo()
            ok = apply_move(self.current_voxels, self._move_src, dst)
            msg = f"移动 {self._move_src} → {dst}" if ok else "移动失败（目标被占或越界）"
            if ok:
                self._sel_pos = dst
                changed_n = 1
            self._move_src = None
            if not ok:
                self._undo_stack._undo.pop()
                self._set_status(msg)
                return
            self._after_voxel_edit(msg)
            return
        else:
            self._undo_stack._undo.pop()
            return

        if not changed_n:
            self._undo_stack._undo.pop()
            self._set_status(msg)
            return
        self._after_voxel_edit(msg)

    def on_nudge_selection(self, delta: tuple[int, int, int]) -> None:
        if self.current_voxels is None or self._sel_pos is None:
            self._set_status("先用「选择」点选一个方块")
            return
        self._push_undo()
        new_pos = nudge(self.current_voxels, self._sel_pos, delta)
        if new_pos is None:
            self._undo_stack._undo.pop()
            self._set_status("微调失败（越界或目标被占）")
            return
        self._sel_pos = new_pos
        self._after_voxel_edit(f"已微调到 {new_pos}")

    def _on_canvas_key(self, event) -> None:
        key = getattr(event, "keysym", "") or ""
        state = int(getattr(event, "state", 0) or 0)
        ctrl = bool(state & 0x4)  # Control on Windows Tk

        if ctrl and key.lower() == "z":
            self.on_undo()
            return
        if ctrl and key.lower() == "y":
            self.on_redo()
            return
        if ctrl and key.lower() == "c":
            self.on_copy_selection()
            return
        if ctrl and key.lower() == "x":
            self.on_cut_selection()
            return
        if ctrl and key.lower() == "v":
            self.on_paste_at_selection()
            return

        if (not ctrl) and key in ("1", "2", "3", "4", "5", "6", "7", "8", "9"):
            self._select_hotbar(int(key) - 1)
            return

        if self._mode != MODE_EDIT or self._sel_pos is None:
            return
        mapping = {
            "Left": (-1, 0, 0),
            "Right": (1, 0, 0),
            "Up": (0, 0, -1),
            "Down": (0, 0, 1),
            "Prior": (0, 1, 0),  # PageUp
            "Next": (0, -1, 0),  # PageDown
            "Delete": None,
            "BackSpace": None,
        }
        if key in ("Delete", "BackSpace"):
            self._push_undo()
            if apply_break(self.current_voxels, self._sel_pos):
                self._sel_pos = None
                if hasattr(self, "sel_pos_label"):
                    self.sel_pos_label.configure(text="选中：无")
                self._after_voxel_edit("已删除选中方块")
            else:
                self._undo_stack._undo.pop()
            return
        delta = mapping.get(key)
        if delta is not None:
            self.on_nudge_selection(delta)

def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="MC architecture AI sample 3D preview")
    parser.add_argument(
        "--samples",
        "--out-dir",
        dest="out_dir",
        default=None,
        help="Sample directory (default: newest outputs/design/*/npz, else configs sample.out_dir)",
    )
    args = parser.parse_args()
    app = ViewerApp(out_dir=args.out_dir)
    app.mainloop()


if __name__ == "__main__":
    main()
