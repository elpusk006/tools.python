import csv
from datetime import datetime
import fnmatch
import hashlib
import os
import queue
import subprocess
import sys
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

FONT_FAMILY = "맑은 고딕" if sys.platform == "win32" else "sans-serif"
MONO_FONT = ("Consolas", 9) if sys.platform == "win32" else ("monospace", 9)


class FileMatcherApp:
    def __init__(self, root):
        self.root = root
        self.root.title("배포본 - 원본 파일 매칭 프로그램")
        self.root.geometry("1080x760")
        self.root.minsize(880, 620)

        # UI 스타일 설정
        style = ttk.Style()
        style.theme_use('clam')
        style.configure("Treeview.Heading", font=(FONT_FAMILY, 9, "bold"))
        style.configure("Treeview", font=(FONT_FAMILY, 9), rowheight=24)

        # 데이터 저장소
        self.src_files = []
        self.dst_files = []
        self.matched_files = []
        self._parent_id_cache = {}

        # 백그라운드 작업 및 스레드 통신 큐
        self.ui_queue = queue.Queue()
        self.stop_event = threading.Event()
        self.worker_thread = None

        self.create_widgets()

        # 창 닫기 이벤트 핸들러 및 큐 폴링 시작
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.check_queue()

    def create_widgets(self):
        # --- 입력 영역 프레임 ---
        input_frame = ttk.LabelFrame(self.root, text=" 설정 및 경로 입력 ", padding=10)
        input_frame.pack(fill="x", padx=15, pady=8)

        # 1 & 2. 배포 파일 설정 (dsrc, fsrc)
        ttk.Label(input_frame, text="1. 배포 디렉토리 (dsrc):").grid(row=0, column=0, sticky="w", pady=4)
        self.entry_dsrc = ttk.Entry(input_frame, width=50)
        self.entry_dsrc.grid(row=0, column=1, padx=5, pady=4, sticky="ew")
        ttk.Button(input_frame, text="찾아보기...", command=self.browse_dsrc).grid(row=0, column=2, padx=5, pady=4)

        ttk.Label(input_frame, text="2. 배포 파일 형식 (fsrc):").grid(row=1, column=0, sticky="w", pady=4)
        self.entry_fsrc = ttk.Entry(input_frame, width=20)
        self.entry_fsrc.insert(0, "*.bin")
        self.entry_fsrc.grid(row=1, column=1, padx=5, pady=4, sticky="w")

        # 구분선
        ttk.Separator(input_frame, orient="horizontal").grid(row=2, column=0, columnspan=3, sticky="ew", pady=6)

        # 3 & 4. 원본 파일 설정 (ddst, fdst)
        ttk.Label(input_frame, text="3. 원본 디렉토리 (ddst):").grid(row=3, column=0, sticky="w", pady=4)
        self.entry_ddst = ttk.Entry(input_frame, width=50)
        self.entry_ddst.grid(row=3, column=1, padx=5, pady=4, sticky="ew")
        ttk.Button(input_frame, text="찾아보기...", command=self.browse_ddst).grid(row=3, column=2, padx=5, pady=4)

        ttk.Label(input_frame, text="4. 원본 파일 형식 (fdst):").grid(row=4, column=0, sticky="w", pady=4)
        self.entry_fdst = ttk.Entry(input_frame, width=20)
        self.entry_fdst.insert(0, "*.bin")
        self.entry_fdst.grid(row=4, column=1, padx=5, pady=4, sticky="w")

        input_frame.columnconfigure(1, weight=1)

        # --- 제어 버튼 및 상태 영역 ---
        btn_bar = ttk.Frame(self.root, padding=(15, 4))
        btn_bar.pack(fill="x")

        self.btn_run = ttk.Button(btn_bar, text="▶ 검색 및 SHA-1 비교 시작", command=self.run_matching)
        self.btn_run.pack(side="left", padx=(0, 6))

        self.btn_stop = ttk.Button(btn_bar, text="■ 작업 중단", command=self.stop_matching, state="disabled")
        self.btn_stop.pack(side="left", padx=(0, 8))

        self.btn_export_all = ttk.Button(btn_bar, text="모든 결과 CSV 일괄 저장", command=self.export_all_csv)
        self.btn_export_all.pack(side="left", padx=5)

        self.prog_bar = ttk.Progressbar(btn_bar, mode="indeterminate", length=140)
        self.prog_bar.pack(side="left", padx=10)

        self.lbl_status = ttk.Label(btn_bar, text="준비됨", foreground="#555555")
        self.lbl_status.pack(side="right", padx=5)

        # --- 탭(Notebook) 결과 영역 ---
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill="both", expand=True, padx=15, pady=(5, 10))

        # 탭 1: 배포 파일 작업 결과 리스트
        self.tab_src = ttk.Frame(self.notebook, padding=5)
        self.notebook.add(self.tab_src, text=" 배포 파일 결과 (0) ")
        self.create_src_tab()

        # 탭 2: 원본 파일 작업 결과 리스트
        self.tab_dst = ttk.Frame(self.notebook, padding=5)
        self.notebook.add(self.tab_dst, text=" 원본 파일 결과 (0) ")
        self.create_dst_tab()

        # 탭 3: 매칭 결과 리스트 (Treeview 계층 표시 지원)
        self.tab_match = ttk.Frame(self.notebook, padding=5)
        self.notebook.add(self.tab_match, text=" 매칭 결과 (0) ")
        self.create_match_tab()

        # 탭 4: 상세 로그
        self.tab_log = ttk.Frame(self.notebook, padding=5)
        self.notebook.add(self.tab_log, text=" 작업 로그 ")
        self.create_log_tab()

    def create_treeview_with_scrollbars(self, parent, columns, show="headings"):
        """Treeview와 수평/수직 스크롤바를 포함하는 프레임을 생성합니다."""
        frame = ttk.Frame(parent)
        frame.pack(fill="both", expand=True)

        tree = ttk.Treeview(frame, columns=columns, show=show, selectmode="browse")
        vsb = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
        hsb = ttk.Scrollbar(frame, orient="horizontal", command=tree.xview)
        tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)

        vsb.pack(side="right", fill="y")
        hsb.pack(side="bottom", fill="x")
        tree.pack(side="left", fill="both", expand=True)

        return frame, tree

    def setup_tree_columns(self, tree, col_defs, tree_col_def=None):
        """컬럼 너비, 정렬 및 정렬 이벤트를 설정합니다."""
        if tree_col_def:
            col_name, width, anchor = tree_col_def
            tree.heading("#0", text=col_name, command=lambda: self.sort_treeview_column(tree, "#0", False))
            tree.column("#0", width=width, anchor=anchor)

        for col_id, col_name, width, anchor in col_defs:
            tree.heading(col_id, text=col_name, command=lambda c=col_id: self.sort_treeview_column(tree, c, False))
            tree.column(col_id, width=width, anchor=anchor)

    def sort_treeview_column(self, tree, col, reverse):
        """컬럼 헤더 클릭 시 루트 노드들을 기준으로 정렬을 수행합니다."""
        if col == "#0":
            data_list = [(tree.item(child, "text"), child) for child in tree.get_children('')]
        else:
            data_list = [(tree.set(child, col), child) for child in tree.get_children('')]

        try:
            # 숫자 정렬 시도
            data_list.sort(key=lambda t: int(str(t[0]).replace(',', '')), reverse=reverse)
        except (ValueError, TypeError):
            # 문자열 정렬
            data_list.sort(key=lambda t: str(t[0]).lower(), reverse=reverse)

        for idx, (_, item) in enumerate(data_list):
            tree.move(item, '', idx)

        tree.heading(col, command=lambda: self.sort_treeview_column(tree, col, not reverse))

    def create_src_tab(self):
        col_defs = [
            ("no", "번호", 50, "center"),
            ("filename", "파일명", 180, "w"),
            ("ext", "확장자", 65, "center"),
            ("size", "크기 (Bytes)", 95, "e"),
            ("sha1", "SHA-1 해시", 300, "center"),
            ("dir", "디렉토리 위치", 200, "w"),
            ("full_path", "전체 파일 경로", 350, "w")
        ]
        _, self.tree_src = self.create_treeview_with_scrollbars(self.tab_src, [c[0] for c in col_defs], show="headings")
        self.setup_tree_columns(self.tree_src, col_defs)
        self.tree_src.bind("<Double-1>", lambda event: self.open_in_explorer(self.tree_src, "full_path"))

        # 하단 바
        bottom_bar = ttk.Frame(self.tab_src, padding=(0, 6, 0, 0))
        bottom_bar.pack(fill="x")
        self.lbl_src_count = ttk.Label(bottom_bar, text="총 0개 파일 (항목 더블클릭 시 탐색기 위치 열기)")
        self.lbl_src_count.pack(side="left")
        btn_export = ttk.Button(bottom_bar, text="배포 파일 목록 CSV 내보내기", command=lambda: self.export_csv("src"))
        btn_export.pack(side="right")

    def create_dst_tab(self):
        col_defs = [
            ("no", "번호", 50, "center"),
            ("filename", "파일명", 180, "w"),
            ("ext", "확장자", 65, "center"),
            ("size", "크기 (Bytes)", 95, "e"),
            ("sha1", "SHA-1 해시", 300, "center"),
            ("dir", "디렉토리 위치", 200, "w"),
            ("full_path", "전체 파일 경로", 350, "w")
        ]
        _, self.tree_dst = self.create_treeview_with_scrollbars(self.tab_dst, [c[0] for c in col_defs], show="headings")
        self.setup_tree_columns(self.tree_dst, col_defs)
        self.tree_dst.bind("<Double-1>", lambda event: self.open_in_explorer(self.tree_dst, "full_path"))

        # 하단 바
        bottom_bar = ttk.Frame(self.tab_dst, padding=(0, 6, 0, 0))
        bottom_bar.pack(fill="x")
        self.lbl_dst_count = ttk.Label(bottom_bar, text="총 0개 파일 (항목 더블클릭 시 탐색기 위치 열기)")
        self.lbl_dst_count.pack(side="left")
        btn_export = ttk.Button(bottom_bar, text="원본 파일 목록 CSV 내보내기", command=lambda: self.export_csv("dst"))
        btn_export.pack(side="right")

    def create_match_tab(self):
        col_defs = [
            ("match_type", "매칭 구분", 130, "center"),
            ("sha1", "SHA-1 해시", 290, "center"),
            ("src_path", "배포본 전체 경로", 320, "w"),
            ("dst_path", "원본 전체 경로", 350, "w")
        ]
        tree_col_def = ("배포 파일명 / 매칭 원본 파일", 300, "w")

        self._all_expanded = True

        # --- 상단 툴바 (원클릭 접기/펼치기 전용 컨트롤) ---
        top_bar = ttk.Frame(self.tab_match, padding=(0, 2, 0, 6))
        top_bar.pack(fill="x")

        self.btn_toggle_match_top = ttk.Button(
            top_bar,
            text="⊟ 모든 항목 한번에 접기",
            command=self.toggle_all_match
        )
        self.btn_toggle_match_top.pack(side="left", padx=(0, 6))

        btn_top_expand = ttk.Button(
            top_bar,
            text="⊞ 모두 펼치기",
            command=self.expand_all_match
        )
        btn_top_expand.pack(side="left", padx=2)

        btn_top_collapse = ttk.Button(
            top_bar,
            text="⊟ 모두 접기",
            command=self.collapse_all_match
        )
        btn_top_collapse.pack(side="left", padx=2)

        ttk.Label(
            top_bar,
            text="(단축키: Ctrl+E 펼치기 / Ctrl+W 접기 | 우클릭 메뉴 지원)",
            foreground="#666666"
        ).pack(side="left", padx=10)

        # 트리 계층(#0) 및 헤더 활성화
        _, self.tree_match = self.create_treeview_with_scrollbars(
            self.tab_match, [c[0] for c in col_defs], show=("tree", "headings")
        )
        self.setup_tree_columns(self.tree_match, col_defs, tree_col_def=tree_col_def)

        # 계층 스타일 태그 설정
        self.tree_match.tag_configure('multi_parent', background='#EBF3FB', font=(FONT_FAMILY, 9, "bold"))
        self.tree_match.tag_configure('multi_child', background='#F9FAFB')
        self.tree_match.tag_configure('single_match', background='#FFFFFF')

        # 이벤트 및 단축키 바인딩
        self.tree_match.bind("<Double-1>", self.on_match_double_click)
        self.tree_match.bind("<Button-3>", self.show_match_context_menu)
        self.root.bind("<Control-e>", lambda e: self.expand_all_match())
        self.root.bind("<Control-E>", lambda e: self.expand_all_match())
        self.root.bind("<Control-w>", lambda e: self.collapse_all_match())
        self.root.bind("<Control-W>", lambda e: self.collapse_all_match())

        # 우클릭 컨텍스트 메뉴 생성
        self.match_context_menu = tk.Menu(self.root, tearoff=0)
        self.match_context_menu.add_command(label="⊞ 모든 항목 펼치기 (Ctrl+E)", command=self.expand_all_match)
        self.match_context_menu.add_command(label="⊟ 모든 항목 접기 (Ctrl+W)", command=self.collapse_all_match)
        self.match_context_menu.add_separator()
        self.match_context_menu.add_command(label="📁 파일 위치 열기 (탐색기)", command=self.open_selected_match_in_explorer)
        self.match_context_menu.add_command(label="💾 매칭 결과 CSV 내보내기", command=lambda: self.export_csv("match"))

        # 하단 바
        bottom_bar = ttk.Frame(self.tab_match, padding=(0, 6, 0, 0))
        bottom_bar.pack(fill="x")

        self.lbl_match_count = ttk.Label(
            bottom_bar,
            text="총 0개 일치 (항목 더블클릭 시 해당 파일 탐색기 열기)"
        )
        self.lbl_match_count.pack(side="left")

        btn_export = ttk.Button(bottom_bar, text="매칭 결과 CSV 내보내기", command=lambda: self.export_csv("match"))
        btn_export.pack(side="right", padx=(5, 0))

        btn_collapse = ttk.Button(bottom_bar, text="모두 접기", command=self.collapse_all_match)
        btn_collapse.pack(side="right", padx=2)

        btn_expand = ttk.Button(bottom_bar, text="모두 펼치기", command=self.expand_all_match)
        btn_expand.pack(side="right", padx=2)

        self.btn_toggle_match_bot = ttk.Button(
            bottom_bar,
            text="⊟ 한번에 접기",
            command=self.toggle_all_match
        )
        self.btn_toggle_match_bot.pack(side="right", padx=4)

    def set_all_tree_open(self, tree, open_state):
        """Treeview의 모든 부모/자식 노드를 재귀적으로 펼치거나 접습니다."""
        def _recurse(item):
            tree.item(item, open=open_state)
            for child in tree.get_children(item):
                _recurse(child)

        for root_item in tree.get_children(''):
            _recurse(root_item)

    def toggle_all_match(self):
        """매칭 리스트의 모든 Treeview 항목을 한 번에 접기/펼치기 토글합니다."""
        self._all_expanded = not getattr(self, '_all_expanded', True)
        self.set_all_tree_open(self.tree_match, self._all_expanded)
        self._update_expand_button_labels()

    def expand_all_match(self):
        """매칭 트리의 모든 노드를 한 번에 펼칩니다."""
        self._all_expanded = True
        self.set_all_tree_open(self.tree_match, True)
        self._update_expand_button_labels()

    def collapse_all_match(self):
        """매칭 트리의 모든 노드를 한 번에 접습니다."""
        self._all_expanded = False
        self.set_all_tree_open(self.tree_match, False)
        self._update_expand_button_labels()

    def _update_expand_button_labels(self):
        """접기/펼치기 토글 버튼 라벨을 동기화합니다."""
        is_exp = getattr(self, '_all_expanded', True)
        top_text = "⊟ 모든 항목 한번에 접기" if is_exp else "⊞ 모든 항목 한번에 펼치기"
        bot_text = "⊟ 한번에 접기" if is_exp else "⊞ 한번에 펼치기"
        if hasattr(self, 'btn_toggle_match_top'):
            self.btn_toggle_match_top.config(text=top_text)
        if hasattr(self, 'btn_toggle_match_bot'):
            self.btn_toggle_match_bot.config(text=bot_text)

    def show_match_context_menu(self, event):
        """마우스 우클릭 시 컨텍스트 메뉴를 표시합니다."""
        row_id = self.tree_match.identify_row(event.y)
        if row_id:
            self.tree_match.selection_set(row_id)
        self.match_context_menu.post(event.x_root, event.y_root)

    def open_selected_match_in_explorer(self):
        """현재 선택된 매칭 항목의 파일을 탐색기에서 엽니다."""
        self.on_match_double_click(None)

    def create_log_tab(self):
        frame = ttk.Frame(self.tab_log)
        frame.pack(fill="both", expand=True)

        self.txt_output = tk.Text(frame, wrap="word", font=MONO_FONT)
        scrollbar = ttk.Scrollbar(frame, command=self.txt_output.yview)
        self.txt_output.configure(yscrollcommand=scrollbar.set)

        scrollbar.pack(side="right", fill="y")
        self.txt_output.pack(side="left", fill="both", expand=True)

    def open_in_explorer(self, tree, col_key):
        """선택된 항목의 파일 위치를 윈도우 탐색기에서 엽니다."""
        selected_item = tree.selection()
        if not selected_item:
            return
        values = tree.item(selected_item[0], "values")
        cols = tree["columns"]
        if col_key in cols:
            idx = cols.index(col_key)
            filepath = values[idx]
            self.open_file_path_in_explorer(filepath)

    def on_match_double_click(self, event):
        """매칭 트리 항목 더블클릭 시 파일 위치를 엽니다."""
        selected_item = self.tree_match.selection()
        if not selected_item:
            return
        item_id = selected_item[0]
        values = self.tree_match.item(item_id, "values")
        parent_id = self.tree_match.parent(item_id)

        if not values or len(values) < 4:
            return

        src_path = values[2]
        dst_path = values[3]

        if parent_id:
            # 다수 매칭 자식 노드 -> 원본 파일 우선 열기
            target = dst_path if os.path.exists(dst_path) else src_path
        else:
            # 부모 노드 또는 1:1 매칭 노드
            if "1:1" in values[0]:
                target = dst_path if os.path.exists(dst_path) else src_path
            else:
                # 1:N 매칭 부모 노드 -> 배포본 파일 열기
                target = src_path

        self.open_file_path_in_explorer(target)

    def open_file_path_in_explorer(self, filepath):
        if filepath and os.path.exists(filepath):
            norm_path = os.path.normpath(filepath)
            if sys.platform == "win32":
                subprocess.Popen(f'explorer /select,"{norm_path}"')
            elif sys.platform == "darwin":
                subprocess.Popen(["open", "-R", norm_path])
            else:
                # Linux: xdg-open 등으로 파일이 위치한 디렉토리 열기
                target_dir = os.path.dirname(norm_path) if os.path.isfile(norm_path) else norm_path
                subprocess.Popen(["xdg-open", target_dir])
        else:
            messagebox.showwarning("경고", f"해당 경로의 파일을 찾을 수 없습니다:\n{filepath}")

    def browse_dsrc(self):
        directory = filedialog.askdirectory()
        if directory:
            self.entry_dsrc.delete(0, tk.END)
            self.entry_dsrc.insert(0, directory)

    def browse_ddst(self):
        directory = filedialog.askdirectory()
        if directory:
            self.entry_ddst.delete(0, tk.END)
            self.entry_ddst.insert(0, directory)

    def check_queue(self):
        """백그라운드 스레드에서 전송된 UI 업데이트 이벤트를 메인 스레드에서 처리합니다."""
        try:
            # UI 반응성을 유지하면서 대량 이벤트(최대 80개)를 프레임당 일괄 처리
            for _ in range(80):
                msg_type, payload = self.ui_queue.get_nowait()
                if msg_type == 'status':
                    self.lbl_status.config(text=payload)
                elif msg_type == 'log':
                    self.txt_output.insert(tk.END, payload + "\n")
                    self.txt_output.see(tk.END)
                elif msg_type == 'tab_select':
                    self.notebook.select(payload)
                elif msg_type == 'tab_title':
                    idx, title = payload
                    self.notebook.tab(idx, text=title)
                elif msg_type == 'src_item':
                    self.tree_src.insert("", tk.END, values=payload)
                elif msg_type == 'dst_item':
                    self.tree_dst.insert("", tk.END, values=payload)
                elif msg_type == 'src_count':
                    self.lbl_src_count.config(text=payload)
                elif msg_type == 'dst_count':
                    self.lbl_dst_count.config(text=payload)
                elif msg_type == 'match_single':
                    text_label, values = payload
                    self.tree_match.insert("", tk.END, text=text_label, values=values, tags=('single_match',))
                elif msg_type == 'match_parent':
                    parent_key, text_label, values = payload
                    parent_id = self.tree_match.insert("", tk.END, text=text_label, values=values, open=True, tags=('multi_parent',))
                    self._parent_id_cache[parent_key] = parent_id
                elif msg_type == 'match_child':
                    parent_key, text_label, values = payload
                    parent_id = self._parent_id_cache.get(parent_key)
                    if parent_id:
                        self.tree_match.insert(parent_id, tk.END, text=text_label, values=values, tags=('multi_child',))
                elif msg_type == 'match_count':
                    self.lbl_match_count.config(text=payload)
                elif msg_type == 'completed':
                    status_type, data = payload
                    self.on_work_completed(status_type, data)
                self.ui_queue.task_done()
        except queue.Empty:
            pass
        finally:
            self.root.after(30, self.check_queue)

    def log(self, text):
        """로그 탭 텍스트 창에 직접 로그를 출력합니다 (메인 스레드용)."""
        self.txt_output.insert(tk.END, text + "\n")
        self.txt_output.see(tk.END)

    def set_status(self, text):
        """상태 라벨을 직접 업데이트합니다 (메인 스레드용)."""
        self.lbl_status.config(text=text)

    def ui_log(self, text):
        """백그라운드 스레드에서 큐로 로그를 보냅니다."""
        self.ui_queue.put(('log', text))

    def ui_set_status(self, text):
        """백그라운드 스레드에서 큐로 상태 메시지를 보냅니다."""
        self.ui_queue.put(('status', text))

    def stop_matching(self):
        """사용자가 중단 버튼을 눌렀을 때 호출됩니다."""
        if self.worker_thread and self.worker_thread.is_alive():
            self.stop_event.set()
            self.btn_stop.config(state="disabled")
            self.lbl_status.config(text="작업 중단 요청 중...")
            self.log("\n[알림] 사용자가 중단을 요청했습니다. 안전하게 정지 중...")

    def on_closing(self):
        """프로그램 종료 시 백그라운드 스레드를 안전하게 정리합니다."""
        if self.worker_thread and self.worker_thread.is_alive():
            if messagebox.askyesno("종료 확인", "현재 검색/비교 작업이 실행 중입니다.\n작업을 중단하고 프로그램을 종료하시겠습니까?"):
                self.stop_event.set()
                self.root.destroy()
        else:
            self.root.destroy()

    def calculate_sha1(self, file_path):
        """파일의 SHA-1 해시를 계산합니다. 중단 요청 시 조기 종료됩니다."""
        sha1 = hashlib.sha1()
        try:
            with open(file_path, 'rb') as f:
                while chunk := f.read(65536):
                    if self.stop_event.is_set():
                        return None
                    sha1.update(chunk)
            return sha1.hexdigest()
        except (PermissionError, FileNotFoundError, OSError):
            return None

    def find_and_process_files(self, directory, pattern, label, item_type, count_type):
        """디렉토리를 재귀 탐색하며 파일을 찾아 해시를 계산합니다 (워커 스레드에서 실행)."""
        self.ui_log(f"\n--- [{label}] 파일 검색 및 해시 계산 시작 ({directory}) ---")
        matched_files = []
        count = 0

        for root, dirs, files in os.walk(directory):
            if self.stop_event.is_set():
                break
            for filename in fnmatch.filter(files, pattern):
                if self.stop_event.is_set():
                    break
                full_path = os.path.join(root, filename)
                name, ext = os.path.splitext(filename)
                try:
                    file_size = os.path.getsize(full_path)
                except OSError:
                    file_size = 0

                sha1_val = self.calculate_sha1(full_path)
                if self.stop_event.is_set():
                    break
                if sha1_val:
                    count += 1
                    file_item = {
                        'no': count,
                        'filename': filename,
                        'name': name,
                        'ext': ext,
                        'size': file_size,
                        'sha1': sha1_val,
                        'dir': root,
                        'full_path': full_path
                    }
                    matched_files.append(file_item)

                    values = (
                        count,
                        filename,
                        ext,
                        f"{file_size:,}",
                        sha1_val,
                        root,
                        full_path
                    )
                    self.ui_queue.put((item_type, values))
                    self.ui_log(f"[{count}] {filename} ({ext}) | SHA-1: {sha1_val} | 위치: {root}")

                    if count % 10 == 0:
                        self.ui_queue.put((count_type, f"검색 진행 중: {count}개 발견..."))
                        self.ui_set_status(f"{label} 처리 중: {count}개...")

        if not self.stop_event.is_set():
            self.ui_queue.put((count_type, f"총 {count}개 파일 (항목 더블클릭 시 탐색기 위치 열기)"))
            self.ui_log(f"[{label}] 총 {count}개 파일 처리 완료.")
        return matched_files

    def run_matching(self):
        """입력 검증 후 백그라운드 워커 스레드를 시작합니다."""
        dsrc = self.entry_dsrc.get().strip()
        fsrc = self.entry_fsrc.get().strip()
        ddst = self.entry_ddst.get().strip()
        fdst = self.entry_fdst.get().strip()

        if not dsrc or not ddst:
            messagebox.showwarning("경고", "배포 디렉토리와 원본 디렉토리 경로를 모두 입력해주세요.")
            return

        if not os.path.exists(dsrc) or not os.path.exists(ddst):
            messagebox.showerror("에러", "존재하지 않는 디렉토리 경로가 있습니다.")
            return

        # UI 초기화
        self.txt_output.delete("1.0", tk.END)
        for item in self.tree_src.get_children():
            self.tree_src.delete(item)
        for item in self.tree_dst.get_children():
            self.tree_dst.delete(item)
        for item in self.tree_match.get_children():
            self.tree_match.delete(item)

        self.src_files.clear()
        self.dst_files.clear()
        self.matched_files.clear()
        self._parent_id_cache.clear()

        self.notebook.tab(0, text=" 배포 파일 결과 (0) ")
        self.notebook.tab(1, text=" 원본 파일 결과 (0) ")
        self.notebook.tab(2, text=" 매칭 결과 (0) ")
        self.lbl_src_count.config(text="총 0개 파일 (항목 더블클릭 시 탐색기 위치 열기)")
        self.lbl_dst_count.config(text="총 0개 파일 (항목 더블클릭 시 탐색기 위치 열기)")
        self.lbl_match_count.config(text="총 0개 일치 (항목 더블클릭 시 해당 파일 탐색기 열기)")

        self._all_expanded = True
        self._update_expand_button_labels()

        # 버튼 및 진행바 활성화
        self.btn_run.config(state="disabled")
        self.btn_stop.config(state="normal")
        self.btn_export_all.config(state="disabled")
        self.prog_bar.start(10)

        self.stop_event.clear()
        self.worker_thread = threading.Thread(
            target=self._matching_worker,
            args=(dsrc, fsrc, ddst, fdst),
            daemon=True
        )
        self.worker_thread.start()

    def _matching_worker(self, dsrc, fsrc, ddst, fdst):
        """백그라운드 스레드에서 파일 검색, 해시 계산 및 매칭을 순차 실행합니다."""
        try:
            # 1. 배포 파일 처리
            self.ui_queue.put(('tab_select', 0))
            self.ui_set_status("배포 파일 검색 및 해시 계산 중...")
            src_res = self.find_and_process_files(
                dsrc, fsrc, "배포(src)", 'src_item', 'src_count'
            )
            self.src_files.extend(src_res)
            self.ui_queue.put(('tab_title', (0, f" 배포 파일 결과 ({len(self.src_files)}) ")))

            if self.stop_event.is_set():
                self.ui_queue.put(('completed', ('cancelled', None)))
                return

            # 2. 원본 파일 처리
            self.ui_queue.put(('tab_select', 1))
            self.ui_set_status("원본 파일 검색 및 해시 계산 중...")
            dst_res = self.find_and_process_files(
                ddst, fdst, "원본(dst)", 'dst_item', 'dst_count'
            )
            self.dst_files.extend(dst_res)
            self.ui_queue.put(('tab_title', (1, f" 원본 파일 결과 ({len(self.dst_files)}) ")))

            if self.stop_event.is_set():
                self.ui_queue.put(('completed', ('cancelled', None)))
                return

            # 3. SHA-1 비교 및 매칭
            self.ui_queue.put(('tab_select', 2))
            self.ui_set_status("SHA-1 해시 매칭 비교 중...")
            self.ui_log("\n" + "=" * 25 + " SHA-1 매칭 결과 " + "=" * 25)

            dst_dict = {}
            for dst in self.dst_files:
                dst_dict.setdefault(dst['sha1'], []).append(dst)

            match_pair_count = 0
            matched_src_count = 0
            multi_match_count = 0

            for src in self.src_files:
                if self.stop_event.is_set():
                    self.ui_queue.put(('completed', ('cancelled', None)))
                    return

                sha1 = src['sha1']
                if sha1 in dst_dict:
                    matched_dst_list = dst_dict[sha1]
                    matched_src_count += 1
                    num_dsts = len(matched_dst_list)

                    if num_dsts == 1:
                        dst = matched_dst_list[0]
                        match_pair_count += 1
                        match_item = {
                            'no': match_pair_count,
                            'match_type': '1:1 매칭',
                            'sha1': sha1,
                            'src_filename': src['filename'],
                            'dst_filename': dst['filename'],
                            'src_path': src['full_path'],
                            'dst_path': dst['full_path']
                        }
                        self.matched_files.append(match_item)

                        text_label = f"[배포] {src['filename']} → {dst['filename']}"
                        values = (
                            "1:1 매칭",
                            sha1,
                            src['full_path'],
                            dst['full_path']
                        )
                        self.ui_queue.put(('match_single', (text_label, values)))

                        self.ui_log(f"[1:1 매칭] {src['filename']} == {dst['filename']} (SHA-1: {sha1})")
                        self.ui_log(f"  - 배포본: {src['full_path']}")
                        self.ui_log(f"  - 원본  : {dst['full_path']}")
                        self.ui_log("-" * 60)

                    else:
                        multi_match_count += 1
                        parent_key = f"src_{src['no']}_{sha1}"
                        text_label = f"[배포] {src['filename']} (원본 {num_dsts}개 일치)"
                        values = (
                            f"1:N 매칭 ({num_dsts}개)",
                            sha1,
                            src['full_path'],
                            f"하위 {num_dsts}개 원본 파일 확인"
                        )
                        self.ui_queue.put(('match_parent', (parent_key, text_label, values)))

                        self.ui_log(f"[1:N 다수 매칭 ({num_dsts}개)] 배포 파일: {src['filename']} (SHA-1: {sha1})")
                        self.ui_log(f"  - 배포본 위치: {src['full_path']}")

                        for idx, dst in enumerate(matched_dst_list, start=1):
                            if self.stop_event.is_set():
                                self.ui_queue.put(('completed', ('cancelled', None)))
                                return

                            match_pair_count += 1
                            match_item = {
                                'no': match_pair_count,
                                'match_type': f"1:N 매칭 ({idx}/{num_dsts})",
                                'sha1': sha1,
                                'src_filename': src['filename'],
                                'dst_filename': dst['filename'],
                                'src_path': src['full_path'],
                                'dst_path': dst['full_path']
                            }
                            self.matched_files.append(match_item)

                            child_text = f"  └ [원본 #{idx}] {dst['filename']}"
                            child_values = (
                                f"일치 원본 #{idx}",
                                sha1,
                                src['full_path'],
                                dst['full_path']
                            )
                            self.ui_queue.put(('match_child', (parent_key, child_text, child_values)))
                            self.ui_log(f"    ({idx}) {dst['filename']} | {dst['full_path']}")

                        self.ui_log("-" * 60)

            result_summary = {
                'matched_src_count': matched_src_count,
                'multi_match_count': multi_match_count,
                'match_pair_count': match_pair_count
            }
            self.ui_queue.put(('completed', ('success', result_summary)))

        except Exception as e:
            self.ui_queue.put(('completed', ('error', str(e))))

    def on_work_completed(self, status_type, data):
        """작업 완료, 중단 또는 에러 발생 시 UI 상태를 복원하고 결과를 안내합니다."""
        self.prog_bar.stop()
        self.btn_run.config(state="normal")
        self.btn_stop.config(state="disabled")
        self.btn_export_all.config(state="normal")

        if status_type == 'cancelled':
            self.set_status("작업이 사용자에 의해 중단되었습니다.")
            self.log("\n[알림] 작업이 중단되었습니다.")
            messagebox.showinfo("중단됨", "파일 검색 및 비교 작업이 중단되었습니다.")
            return

        if status_type == 'error':
            self.set_status(f"오류 발생: {data}")
            self.log(f"\n[오류] 작업 중 오류가 발생했습니다: {data}")
            messagebox.showerror("오류 발생", f"작업 중 오류가 발생했습니다:\n{data}")
            return

        # 성공 완료
        matched_src_count = data['matched_src_count']
        multi_match_count = data['multi_match_count']
        match_pair_count = data['match_pair_count']

        self.lbl_match_count.config(
            text=f"매칭 배포파일: {matched_src_count}개 (1:1: {matched_src_count - multi_match_count}개, 1:N 다수: {multi_match_count}개) / 원본 매칭 쌍: {match_pair_count}개"
        )
        self.notebook.tab(2, text=f" 매칭 결과 ({matched_src_count}) ")

        if matched_src_count == 0:
            self.log("SHA-1 해시 값이 일치하는 파일을 찾지 못했습니다.")
            self.set_status("매칭 완료: 일치 파일 없음")
        else:
            self.log(f"총 {matched_src_count}개 배포파일(총 {match_pair_count}개 쌍)을 매칭했습니다.")
            self.set_status(f"매칭 완료: 배포파일 {matched_src_count}개 일치 (1:N 다수 매칭: {multi_match_count}개)")

        messagebox.showinfo(
            "완료",
            f"매칭 작업이 완료되었습니다!\n\n"
            f"- 배포 파일 총수: {len(self.src_files)}개\n"
            f"- 원본 파일 총수: {len(self.dst_files)}개\n"
            f"- 매칭된 배포 파일: {matched_src_count}개\n"
            f"  └ 1:1 단일 매칭: {matched_src_count - multi_match_count}개\n"
            f"  └ 1:N 다수 매칭: {multi_match_count}개 (Treeview 계층 표시)\n"
            f"- 매칭된 전체 파일 쌍: {match_pair_count}쌍"
        )

    def export_csv(self, list_type):
        """개별 리스트 데이터를 CSV 파일로 내보냅니다."""
        if self.worker_thread and self.worker_thread.is_alive():
            messagebox.showwarning("안내", "현재 검색/비교 작업이 진행 중입니다.\n작업 완료 또는 중단 후 내보내기를 실행해주세요.")
            return

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        if list_type == "src":
            data = self.src_files
            title = "배포 파일 목록"
            default_name = f"배포파일목록_{timestamp}.csv"
            headers = ["번호", "파일명", "확장자", "크기(Bytes)", "SHA-1", "디렉토리 위치", "전체 경로"]
            keys = ['no', 'filename', 'ext', 'size', 'sha1', 'dir', 'full_path']
        elif list_type == "dst":
            data = self.dst_files
            title = "원본 파일 목록"
            default_name = f"원본파일목록_{timestamp}.csv"
            headers = ["번호", "파일명", "확장자", "크기(Bytes)", "SHA-1", "디렉토리 위치", "전체 경로"]
            keys = ['no', 'filename', 'ext', 'size', 'sha1', 'dir', 'full_path']
        elif list_type == "match":
            data = self.matched_files
            title = "매칭 결과"
            default_name = f"매칭결과_{timestamp}.csv"
            headers = ["번호", "매칭 구분", "SHA-1", "배포 파일명", "원본 파일명", "배포본 전체 경로", "원본 전체 경로"]
            keys = ['no', 'match_type', 'sha1', 'src_filename', 'dst_filename', 'src_path', 'dst_path']
        else:
            return

        if not data:
            messagebox.showwarning("안내", f"내보낼 {title} 데이터가 없습니다.\n먼저 검색 및 비교 작업을 실행해주세요.")
            return

        save_path = filedialog.asksaveasfilename(
            title=f"{title} CSV 저장",
            defaultextension=".csv",
            initialfile=default_name,
            filetypes=[("CSV 파일", "*.csv"), ("모든 파일", "*.*")]
        )

        if not save_path:
            return

        try:
            with open(save_path, mode='w', newline='', encoding='utf-8-sig') as f:
                writer = csv.writer(f)
                writer.writerow(headers)
                for item in data:
                    writer.writerow([item[k] for k in keys])

            messagebox.showinfo("저장 완료", f"{title}가 성공적으로 저장되었습니다:\n{save_path}")
        except Exception as e:
            messagebox.showerror("저장 오류", f"CSV 파일 저장 중 오류가 발생했습니다:\n{str(e)}")

    def export_all_csv(self):
        """배포 파일, 원본 파일, 매칭 결과를 폴더에 각각의 CSV 파일로 일괄 저장합니다."""
        if self.worker_thread and self.worker_thread.is_alive():
            messagebox.showwarning("안내", "현재 검색/비교 작업이 진행 중입니다.\n작업 완료 또는 중단 후 내보내기를 실행해주세요.")
            return

        if not self.src_files and not self.dst_files and not self.matched_files:
            messagebox.showwarning("안내", "내보낼 데이터가 없습니다.\n먼저 검색 및 비교 작업을 실행해주세요.")
            return

        save_dir = filedialog.askdirectory(title="CSV 파일들을 일괄 저장할 폴더를 선택하세요")
        if not save_dir:
            return

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        exported = []

        try:
            # 1. 배포 파일 CSV
            if self.src_files:
                path = os.path.join(save_dir, f"1_배포파일목록_{timestamp}.csv")
                headers = ["번호", "파일명", "확장자", "크기(Bytes)", "SHA-1", "디렉토리 위치", "전체 경로"]
                keys = ['no', 'filename', 'ext', 'size', 'sha1', 'dir', 'full_path']
                with open(path, mode='w', newline='', encoding='utf-8-sig') as f:
                    writer = csv.writer(f)
                    writer.writerow(headers)
                    for item in self.src_files:
                        writer.writerow([item[k] for k in keys])
                exported.append(f"배포 파일 ({len(self.src_files)}건): {os.path.basename(path)}")

            # 2. 원본 파일 CSV
            if self.dst_files:
                path = os.path.join(save_dir, f"2_원본파일목록_{timestamp}.csv")
                headers = ["번호", "파일명", "확장자", "크기(Bytes)", "SHA-1", "디렉토리 위치", "전체 경로"]
                keys = ['no', 'filename', 'ext', 'size', 'sha1', 'dir', 'full_path']
                with open(path, mode='w', newline='', encoding='utf-8-sig') as f:
                    writer = csv.writer(f)
                    writer.writerow(headers)
                    for item in self.dst_files:
                        writer.writerow([item[k] for k in keys])
                exported.append(f"원본 파일 ({len(self.dst_files)}건): {os.path.basename(path)}")

            # 3. 매칭 결과 CSV
            if self.matched_files:
                path = os.path.join(save_dir, f"3_매칭결과_{timestamp}.csv")
                headers = ["번호", "매칭 구분", "SHA-1", "배포 파일명", "원본 파일명", "배포본 전체 경로", "원본 전체 경로"]
                keys = ['no', 'match_type', 'sha1', 'src_filename', 'dst_filename', 'src_path', 'dst_path']
                with open(path, mode='w', newline='', encoding='utf-8-sig') as f:
                    writer = csv.writer(f)
                    writer.writerow(headers)
                    for item in self.matched_files:
                        writer.writerow([item[k] for k in keys])
                exported.append(f"매칭 결과 ({len(self.matched_files)}쌍): {os.path.basename(path)}")

            msg = "다음 CSV 파일들이 성공적으로 생성되었습니다:\n\n" + "\n".join(exported)
            messagebox.showinfo("일괄 저장 완료", msg)

        except Exception as e:
            messagebox.showerror("저장 오류", f"일괄 저장 중 오류가 발생했습니다:\n{str(e)}")


if __name__ == "__main__":
    root = tk.Tk()
    app = FileMatcherApp(root)
    root.mainloop()


