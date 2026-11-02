# -*- coding: utf-8 -*-
from pathlib import Path
import re, ast, shutil

ROOT = Path(__file__).resolve().parents[1]
vp = ROOT / "scripts" / "viewer_app.py"
bak = ROOT / "_xfer" / "viewer_app.py.bak_before_yslice"
if not bak.exists():
    shutil.copy2(vp, bak)
t = vp.read_text(encoding="utf-8")

old_init = "        self.style_perf_var = tk.BooleanVar(value=False)\n        self._mode = MODE_BROWSE"
new_init = (
    "        self.style_perf_var = tk.BooleanVar(value=False)\n"
    "        # Y-slice: show only voxels with y <= value (32 = full for 32^3).\n"
    "        self.y_slice_var = tk.IntVar(value=32)\n"
    "        self._mode = MODE_BROWSE"
)
if old_init not in t:
    raise SystemExit("init missing")
t = t.replace(old_init, new_init, 1)

pat = re.compile(
    r"(self\.style_switch\.grid\(row=7, column=0, sticky=\"w\", padx=4, pady=\(8, 4\)\))\s*"
    r"(self\.info_box = ctk\.CTkTextbox\(parent, height=140\))\s*"
    r"(self\.info_box\.grid\(row=8, column=0, sticky=\"nsew\", padx=4, pady=\(8, 4\)\))",
)
m = pat.search(t)
if not m:
    raise SystemExit("ui grid pattern missing")
insert = (
    m.group(1)
    + "\n\n"
    + "        self.y_slice_label = ctk.CTkLabel(parent, text=\"Y切片（拖低可看室内；32=全高）\")\n"
    + "        self.y_slice_label.grid(row=8, column=0, sticky=\"w\", padx=4, pady=(4, 0))\n"
    + "        self.y_slice_slider = ctk.CTkSlider(\n"
    + "            parent,\n"
    + "            from_=0,\n"
    + "            to=32,\n"
    + "            number_of_steps=32,\n"
    + "            variable=self.y_slice_var,\n"
    + "            command=lambda _v: self._on_y_slice(),\n"
    + "        )\n"
    + "        self.y_slice_slider.grid(row=9, column=0, sticky=\"ew\", padx=4, pady=(0, 4))\n\n"
    + "        "
    + m.group(2)
    + "\n        "
    + m.group(3).replace("row=8", "row=10")
)
t = t[: m.start()] + insert + t[m.end() :]

old_r = (
    "    def render_voxels(self, voxels: np.ndarray) -> None:\n"
    "        perf = bool(self.style_perf_var.get()) if hasattr(self, \"style_perf_var\") else False\n"
    "        info = render_mc_voxels(\n"
    "            self.ax,\n"
    "            self.fig,\n"
    "            voxels,\n"
    "            self.palette,\n"
    "            highlight_id=self._source_id,\n"
    "            performance=perf,\n"
    "        )\n"
    "        self.canvas.draw_idle()\n"
    "        self._last_render_info = info"
)
new_r = (
    "    def _on_y_slice(self) -> None:\n"
    "        if self.current_voxels is None:\n"
    "            return\n"
    "        self.render_voxels(self.current_voxels)\n"
    "\n"
    "    def render_voxels(self, voxels: np.ndarray) -> None:\n"
    "        perf = bool(self.style_perf_var.get()) if hasattr(self, \"style_perf_var\") else False\n"
    "        work = np.asarray(voxels, dtype=np.int16)\n"
    "        y_cut = int(self.y_slice_var.get()) if hasattr(self, \"y_slice_var\") else 99\n"
    "        if work.ndim == 3 and y_cut < work.shape[1] - 1:\n"
    "            work = work.copy()\n"
    "            work[:, y_cut + 1 :, :] = 0\n"
    "        info = render_mc_voxels(\n"
    "            self.ax,\n"
    "            self.fig,\n"
    "            work,\n"
    "            self.palette,\n"
    "            highlight_id=self._source_id,\n"
    "            performance=perf,\n"
    "        )\n"
    "        info = dict(info)\n"
    "        info[\"y_slice\"] = y_cut\n"
    "        self.canvas.draw_idle()\n"
    "        self._last_render_info = info"
)
if old_r not in t:
    raise SystemExit("render missing")
t = t.replace(old_r, new_r, 1)
ast.parse(t)
vp.write_text(t, encoding="utf-8")
print("viewer OK", len(t))
