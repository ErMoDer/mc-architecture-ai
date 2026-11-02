
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

