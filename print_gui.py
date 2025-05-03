import cat_printer
import image_processor
import sys
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                            QHBoxLayout, QLabel, QLineEdit, QPushButton, 
                            QListWidget, QListWidgetItem, QScrollArea, 
                            QFrame, QSizePolicy, QFileDialog, QGridLayout, QCheckBox)
from PyQt6.QtGui import QPixmap, QIcon, QColor, QPalette
from PyQt6.QtCore import Qt, QSize, QThread, pyqtSignal
import os
from PIL import Image

class ImagePreviewWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.layout = QVBoxLayout()
        self.setLayout(self.layout)
        
        # 이미지 목록을 위한 스크롤 영역
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_content = QWidget()
        self.grid_layout = QGridLayout(self.scroll_content)
        self.scroll_area.setWidget(self.scroll_content)
        
        # 시스템 테마 색상 가져오기
        palette = self.palette()
        background_color = palette.color(QPalette.ColorRole.Window).name()
        border_color = palette.color(QPalette.ColorRole.Mid).name()
        
        # 스크롤 영역 스타일 설정 (테두리와 배경색)
        self.scroll_area.setStyleSheet(f"QScrollArea {{ border: 2px solid {border_color}; background-color: {background_color}; }}")
        
        self.layout.addWidget(self.scroll_area)
        
        self.image_widgets = []
        self.image_paths = []
        self.item_width = 220  # 각 항목의 너비
        self.current_row = 0
        self.current_col = 0

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.rearrange_grid()

    def rearrange_grid(self):
        # 사용 가능한 너비에 따라 열 수 계산
        width = self.scroll_area.viewport().width()
        column_count = max(1, width // self.item_width)
        
        # 기존 위젯 재배치
        for i, widget in enumerate(self.image_widgets):
            row = i // column_count
            col = i % column_count
            self.grid_layout.addWidget(widget, row, col)
        self.current_row = (len(self.image_widgets) - 1) // column_count if self.image_widgets else 0
        self.current_col = (len(self.image_widgets) - 1) % column_count if self.image_widgets else 0

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.accept()
        else:
            event.ignore()

    def dropEvent(self, event):
        for url in event.mimeData().urls():
            file_path = url.toLocalFile()
            if file_path.lower().endswith((".png", ".jpg", ".jpeg", ".gif", ".bmp")):
                self.add_image(file_path)

    def add_image(self, image_path):
        if image_path not in self.image_paths:
            # 이미지 미리보기 위젯
            frame = QFrame()
            frame.setFrameShape(QFrame.Shape.Box)
            layout = QVBoxLayout()
            frame.setLayout(layout)
            frame.setFixedSize(220, 250)
            
            # 이미지
            pixmap = QPixmap(image_path)
            pixmap = pixmap.scaled(200, 200, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            image_label = QLabel()
            image_label.setPixmap(pixmap)
            image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(image_label)
            
            # 파일명
            filename = os.path.basename(image_path)
            name_label = QLabel(filename)
            name_label.setWordWrap(True)
            name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(name_label)
            
            # 삭제 버튼
            delete_btn = QPushButton("X")
            delete_btn.setFixedSize(30, 30)
            delete_btn.clicked.connect(lambda: self.remove_image(frame, image_path))
            layout.addWidget(delete_btn, alignment=Qt.AlignmentFlag.AlignCenter)
            
            # 격자에 추가
            width = self.scroll_area.viewport().width()
            column_count = max(1, width // self.item_width)
            self.grid_layout.addWidget(frame, self.current_row, self.current_col)
            self.image_widgets.append(frame)
            self.image_paths.append(image_path)
            
            # 다음 위치 계산
            self.current_col += 1
            if self.current_col >= column_count:
                self.current_col = 0
                self.current_row += 1

    def remove_image(self, frame, image_path):
        frame.deleteLater()
        self.image_widgets.remove(frame)
        idx = self.image_paths.index(image_path)
        self.image_paths.pop(idx)
        
        # 격자 재배치
        width = self.scroll_area.viewport().width()
        column_count = max(1, width // self.item_width)
        self.current_row = 0
        self.current_col = 0
        for i, widget in enumerate(self.image_widgets):
            row = i // column_count
            col = i % column_count
            self.grid_layout.addWidget(widget, row, col)
            self.current_row = row
            self.current_col = col

    def get_image_paths(self):
        return self.image_paths

class CatPrinterGUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Cat Printer")
        self.setGeometry(100, 100, 500, 500)
        
        # Initialize logic
        self.printer_logic = PrinterLogic()
        
        # 메인 위젯과 레이아웃
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        layout = QVBoxLayout(main_widget)
        
        # 이미지 경로 입력
        path_layout = QHBoxLayout()
        path_label = QLabel("Image Path:")
        self.path_entry = QLineEdit()
        path_button = QPushButton("Select Image")
        path_button.clicked.connect(self.select_image)
        path_layout.addWidget(path_label)
        path_layout.addWidget(self.path_entry)
        path_layout.addWidget(path_button)
        layout.addLayout(path_layout)
        
        # 이미지 미리보기 영역
        self.image_preview = ImagePreviewWidget()
        layout.addWidget(self.image_preview)
        
        # 프린트 버튼
        print_button = QPushButton("Print")
        print_button.clicked.connect(self.start_printing)
        layout.addWidget(print_button, alignment=Qt.AlignmentFlag.AlignCenter)
        
        # 상태 메시지
        self.status_label = QLabel("")
        layout.addWidget(self.status_label, alignment=Qt.AlignmentFlag.AlignCenter)

    def select_image(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select Image", "", "Image Files (*.png *.jpg *.jpeg *.gif *.bmp)"
        )
        if file_path:
            self.path_entry.setText(file_path)
            self.image_preview.add_image(file_path)

    def start_printing(self):
        image_paths = self.image_preview.get_image_paths()
        if not image_paths:
            self.status_label.setText("No images selected")
            return
        self.status_label.setText(f"Printing {len(image_paths)} image(s)")
        
        # Disable UI elements during printing
        self.set_ui_enabled(False)
        
        # Start printing in a separate thread
        self.print_thread = PrintWorker(self.printer_logic, image_paths)
        self.print_thread.finished.connect(self.on_printing_finished)
        self.print_thread.error.connect(self.on_printing_error)
        self.print_thread.start()

    def on_printing_finished(self):
        self.status_label.setText("Printing completed")
        self.set_ui_enabled(True)

    def on_printing_error(self, error_msg):
        self.status_label.setText(f"Error: {error_msg}")
        self.set_ui_enabled(True)

    def set_ui_enabled(self, enabled):
        self.path_entry.setEnabled(enabled)
        self.image_preview.setEnabled(enabled)
        for child in self.findChildren(QPushButton):
            child.setEnabled(enabled)

class PrinterLogic:
    def __init__(self):
        self.printer = cat_printer.CatPrinter()
        self.is_initialized = False

    def initialize_printer(self):
        """Initialize the printer connection"""
        if not self.is_initialized:
            try:
                self.printer.setup()
                self.is_initialized = True
                return True
            except Exception as e:
                raise Exception(f"Failed to initialize printer: {e}")
        return True

    def print_images(self, image_paths):
        """Print images based on the mode selected"""
        if not image_paths:
            raise ValueError("No images provided for printing")
        
        # Ensure printer is initialized
        self.initialize_printer()
        
        # TODO: Implement print_images
        for path in image_paths:
            try:
                img = Image.open(path)
                self.printer.print_single_image(img)
                self.printer.wait_for_print_completion()
            except Exception as e:
                raise Exception(f"Failed to print image {path}: {e}")

    def close(self):
        """Close the printer connection"""
        if self.is_initialized:
            self.printer.close()
            self.is_initialized = False

class PrintWorker(QThread):
    finished = pyqtSignal()
    error = pyqtSignal(str)

    def __init__(self, printer_logic, image_paths):
        super().__init__()
        self.printer_logic = printer_logic
        self.image_paths = image_paths

    def run(self):
        try:
            self.printer_logic.print_images(self.image_paths)
            self.finished.emit()
        except Exception as e:
            self.error.emit(str(e))

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = CatPrinterGUI()
    window.show()
    try:
        sys.exit(app.exec())
    finally:
        window.printer_logic.close()