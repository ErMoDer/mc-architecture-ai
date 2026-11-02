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

