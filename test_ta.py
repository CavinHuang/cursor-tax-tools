import tkinter as tk
from tkinter import ttk

class TableWithButtons(tk.Frame):
    def __init__(self, parent, data):
        super().__init__(parent)

        self.data = data
        self.buttons = []  # 用于存储按钮，方便后续访问

        self.create_table()

    def create_table(self):
        # 创建表头
        for col_index, header in enumerate(self.data[0]):
            label = tk.Label(self, text=header, relief=tk.SOLID, borderwidth=1)
            label.grid(row=0, column=col_index, padx=5, pady=5, sticky="ew")

        # 创建表格内容和按钮
        for row_index, row_data in enumerate(self.data[1:]):  # 跳过表头行
            for col_index, cell_data in enumerate(row_data):
                if col_index == len(row_data) - 1:  # 假设最后一列放按钮
                    button = tk.Button(self, text="操作", command=lambda row=row_index + 1: self.on_button_click(row))  # row_index 从 0 开始，但数据从第二行开始
                    button.grid(row=row_index + 1, column=col_index, padx=5, pady=5, sticky="ew")
                    self.buttons.append(button)  # 保存按钮引用
                else:
                    label = tk.Label(self, text=cell_data, relief=tk.SOLID, borderwidth=1)
                    label.grid(row=row_index + 1, column=col_index, padx=5, pady=5, sticky="ew")

        # 使列可以拉伸
        for i in range(len(self.data[0])):
            self.grid_columnconfigure(i, weight=1)

    def on_button_click(self, row_index):
        # 在这里处理按钮点击事件
        print(f"按钮被点击，行索引：{row_index}")
        # 你可以在这里访问 self.data[row_index] 获取该行的数据
        # 并且可以根据需要执行相应的操作，例如编辑数据、删除行等。

# 示例数据
data = [
    ["姓名", "年龄", "城市", "操作"],  # 表头
    ["张三", "25", "北京", ""],
    ["李四", "30", "上海", ""],
    ["王五", "28", "广州", ""]
]

# 创建主窗口
root = tk.Tk()
root.title("带按钮的表格")

# 创建表格部件
table = TableWithButtons(root, data)
table.pack(expand=True, fill="both", padx=10, pady=10)  # expand 和 fill 使表格填充窗口

# 运行主循环
root.mainloop()
