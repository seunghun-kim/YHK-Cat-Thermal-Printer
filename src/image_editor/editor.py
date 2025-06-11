import sys
import os
import tempfile
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QPushButton, QScrollArea, QFileDialog,
                             QMessageBox, QLabel, QSizePolicy)
from PySide6.QtCore import Qt, QSize, Signal
from PySide6.QtGui import QPainter, QPixmap, QFont
from PIL import Image, ImageDraw, ImageFont
from .canvas import EditableCanvas


class ImageEditor(QMainWindow):
    # Signal to emit when image is created
    image_created = Signal(str)  # Emits the file path of created image
    
    def __init__(self, image_width=384, on_image_created=None):
        super().__init__()
        self.image_width = image_width
        self.on_image_created = on_image_created  # Callback function
        self.setup_ui()
        
    def setup_ui(self):
        self.setWindowTitle("Image Editor")
        self.setMinimumSize(300 + self.image_width, 500)
        
        # Central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Main layout
        main_layout = QHBoxLayout(central_widget)
        
        # Left panel with buttons
        left_panel = QWidget()
        left_panel.setFixedWidth(200)
        left_layout = QVBoxLayout(left_panel)
        
        # Buttons
        add_text_btn = QPushButton("Add Text")
        add_text_btn.clicked.connect(self.add_text)
        
        add_image_btn = QPushButton("Add Image")
        add_image_btn.clicked.connect(self.add_image)
        
        done_btn = QPushButton("Done")
        done_btn.clicked.connect(self.export_image)
        done_btn.setStyleSheet("QPushButton { background-color: #4CAF50; color: white; font-weight: bold; }")
        
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.close)
        cancel_btn.setStyleSheet("QPushButton { background-color: #f44336; color: white; }")
        
        left_layout.addWidget(add_text_btn)
        left_layout.addWidget(add_image_btn)
        left_layout.addStretch()
        left_layout.addWidget(done_btn)
        left_layout.addWidget(cancel_btn)
        
        # Canvas area
        canvas_area = QWidget()
        canvas_layout = QVBoxLayout(canvas_area)
        
        # Info label
        info_label = QLabel(f"Canvas Width: {self.image_width}px")
        info_label.setAlignment(Qt.AlignCenter)
        canvas_layout.addWidget(info_label)
        
        # Instruction label
        instruction_label = QLabel("Right-click on items for layer options (Bring to Front/Back)")
        instruction_label.setAlignment(Qt.AlignCenter)
        instruction_label.setStyleSheet("QLabel { font-size: 10px; color: gray; }")
        canvas_layout.addWidget(instruction_label)
        
        # Delete instruction label
        delete_label = QLabel("Press Delete/Backspace to remove selected items")
        delete_label.setAlignment(Qt.AlignCenter)
        delete_label.setStyleSheet("QLabel { font-size: 10px; color: gray; }")
        canvas_layout.addWidget(delete_label)
        
        # Scroll area for canvas
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        
        # Canvas
        self.canvas = EditableCanvas(self.image_width)
        self.scroll_area.setWidget(self.canvas)
        
        canvas_layout.addWidget(self.scroll_area)
        
        # Add panels to main layout
        main_layout.addWidget(left_panel)
        main_layout.addWidget(canvas_area, 1)  # Give canvas area more space
        
        # Set focus to canvas for keyboard events
        self.canvas.setFocus()

    def keyPressEvent(self, event):
        """Forward keyboard events to canvas"""
        if event.key() in (Qt.Key_Delete, Qt.Key_Backspace):
            # Forward delete events to canvas
            self.canvas.keyPressEvent(event)
        else:
            super().keyPressEvent(event)

    def add_text(self):
        """Add a new text element to the canvas"""
        self.canvas.add_text_element()
        
    def add_image(self):
        """Add a new image element to the canvas"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, 
            "Select Image", 
            "", 
            "Image Files (*.png *.jpg *.jpeg *.bmp *.gif)"
        )
        
        if file_path:
            self.canvas.add_image_element(file_path)
            
    def export_image(self):
        """Export the canvas as an image and close the editor"""
        try:
            # Get the trimmed height based on content
            trimmed_height = self.canvas.get_content_height()
            
            if trimmed_height == 0:
                QMessageBox.warning(self, "Warning", "No content to export!")
                return
                
            # Create PIL image
            pil_image = Image.new('RGB', (self.image_width, trimmed_height), 'white')
            draw = ImageDraw.Draw(pil_image)
            
            # Render all elements
            self.canvas.render_to_pil_image(pil_image, draw)
            
            # Create temporary file
            temp_dir = tempfile.gettempdir()
            temp_filename = f"cat_printer_image_{os.getpid()}_{id(self)}.png"
            temp_path = os.path.join(temp_dir, temp_filename)
            
            # Save the image to temp path
            pil_image.save(temp_path)
            
            # Emit signal and call callback
            self.image_created.emit(temp_path)
            if self.on_image_created:
                self.on_image_created(temp_path)
            
            # Close the editor
            self.close()
                
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to export image: {str(e)}")


def main():
    app = QApplication(sys.argv)
    
    # Get image width from command line arguments or use default
    image_width = 384
    if len(sys.argv) > 1:
        try:
            image_width = int(sys.argv[1])
        except ValueError:
            print(f"Invalid width value: {sys.argv[1]}. Using default: {image_width}")
    
    editor = ImageEditor(image_width)
    editor.show()
    
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
