from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                             QTextEdit, QFontDialog, QColorDialog, QPushButton,
                             QFrame, QSizePolicy, QGraphicsView, QGraphicsScene,
                             QGraphicsPixmapItem, QGraphicsTextItem, QGraphicsItem)
from PySide6.QtCore import Qt, QRectF, QPointF, Signal, QTimer
from PySide6.QtGui import (QPainter, QPen, QBrush, QFont, QPixmap, QColor, 
                          QTransform, QPainterPath, QFontMetrics)
from PIL import Image, ImageDraw, ImageFont
import os
from .editable_text import EditableTextItem
from .editable_image import EditableImageItem


class EditableCanvas(QWidget):
    def __init__(self, canvas_width):
        super().__init__()
        self.canvas_width = canvas_width
        self.canvas_height = 800  # Initial height, will grow dynamically
        self.elements = []  # List of editable elements
        self.setup_ui()
        
    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Graphics view for canvas
        self.graphics_view = QGraphicsView()
        self.graphics_scene = QGraphicsScene()
        self.graphics_view.setScene(self.graphics_scene)
        
        # Set scene size
        self.graphics_scene.setSceneRect(0, 0, self.canvas_width, self.canvas_height)
        
        # Set canvas background to white
        self.graphics_scene.setBackgroundBrush(QBrush(QColor("white")))
        
        # Configure view
        self.graphics_view.setRenderHint(QPainter.Antialiasing)
        self.graphics_view.setDragMode(QGraphicsView.RubberBandDrag)  # Enable multi-selection
        self.graphics_view.setFrameStyle(QFrame.Box)
        
        # Set view update mode for better performance
        self.graphics_view.setViewportUpdateMode(QGraphicsView.FullViewportUpdate)
        
        # Enable rubber band selection for multi-selection
        self.graphics_view.setRubberBandSelectionMode(Qt.ContainsItemShape)
        
        # Set fixed width for the view
        self.graphics_view.setFixedWidth(self.canvas_width + 20)  # +20 for scrollbar
        
        # Set focus policy to receive keyboard events
        self.graphics_view.setFocusPolicy(Qt.StrongFocus)
        self.setFocusPolicy(Qt.StrongFocus)
        
        layout.addWidget(self.graphics_view)
        
    def add_text_element(self):
        """Add a new editable text element"""
        text_item = EditableTextItem("Double-click to edit")
        text_item.setPos(50, len(self.elements) * 60 + 50)  # Stagger positions
        text_item.setFlag(QGraphicsItem.ItemIsMovable, True)
        text_item.setFlag(QGraphicsItem.ItemIsSelectable, True)
        text_item.setFlag(QGraphicsItem.ItemIsFocusable, True)
        
        # Set Z-value to bring new item to front
        max_z = 0
        if self.elements:
            max_z = max(item.zValue() for item in self.elements)
        text_item.setZValue(max_z + 1)
        
        self.graphics_scene.addItem(text_item)
        self.elements.append(text_item)
        
        # Expand scene if needed
        self.expand_scene_if_needed()
        
        # Force full scene update
        self.graphics_scene.update()
        
    def add_image_element(self, image_path):
        """Add a new editable image element"""
        try:
            image_item = EditableImageItem(image_path)
            image_item.setPos(100, len(self.elements) * 100 + 50)  # Stagger positions
            image_item.setFlag(QGraphicsItem.ItemIsMovable, True)
            image_item.setFlag(QGraphicsItem.ItemIsSelectable, True)
            
            # Set Z-value to bring new item to front
            max_z = 0
            if self.elements:
                max_z = max(item.zValue() for item in self.elements)
            image_item.setZValue(max_z + 1)
            
            self.graphics_scene.addItem(image_item)
            self.elements.append(image_item)
            
            # Expand scene if needed
            self.expand_scene_if_needed()
            
            # Force full scene update
            self.graphics_scene.update()
            
        except Exception as e:
            print(f"Error adding image: {e}")
            
    def expand_scene_if_needed(self):
        """Expand scene height if content goes beyond current bounds"""
        if self.elements:
            max_y = 0
            for element in self.elements:
                item_bottom = element.pos().y() + element.boundingRect().height()
                max_y = max(max_y, item_bottom)
            
            # Add some padding
            needed_height = max_y + 100
            if needed_height > self.canvas_height:
                self.canvas_height = needed_height
                self.graphics_scene.setSceneRect(0, 0, self.canvas_width, self.canvas_height)
                # Force update after scene resize
                self.graphics_scene.update()
                
    def get_content_height(self):
        """Get the height needed to contain all content (for trimming)"""
        if not self.elements:
            return 100  # Minimum height
            
        max_y = 0
        for element in self.elements:
            # Calculate the bottom edge of each element
            item_bottom = element.pos().y() + element.boundingRect().height()
            max_y = max(max_y, item_bottom)
            
        # Add some padding, minimum 100px
        final_height = max(int(max_y) + 20, 100)
        print(f"Content height calculated: {final_height}px (max_y: {max_y})")
        return final_height
        
    def render_to_pil_image(self, pil_image, draw):
        """Render all elements to a PIL image in Z-order"""
        # Sort elements by Z-value (lowest first, highest last)
        # This ensures that items with higher Z-values are drawn on top
        sorted_elements = sorted(self.elements, key=lambda item: item.zValue())
        
        print(f"Rendering {len(sorted_elements)} elements in Z-order:")
        for i, element in enumerate(sorted_elements):
            z_value = element.zValue()
            element_type = "Text" if hasattr(element, 'text_font') else "Image"
            print(f"  {i+1}. {element_type} (Z: {z_value})")
            
        # Render elements in Z-order
        for element in sorted_elements:
            element.render_to_pil(pil_image, draw)
            
    def resizeEvent(self, event):
        """Handle resize events to maintain canvas width"""
        super().resizeEvent(event)
        # Keep the graphics view width fixed to canvas width
        self.graphics_view.setFixedWidth(self.canvas_width + 20) 

    def keyPressEvent(self, event):
        """Handle keyboard events for canvas-level operations"""
        if event.key() in (Qt.Key_Delete, Qt.Key_Backspace):
            self.delete_selected_items()
            event.accept()
        else:
            super().keyPressEvent(event)

    def delete_selected_items(self):
        """Delete all currently selected items"""
        selected_items = self.graphics_scene.selectedItems()
        
        if not selected_items:
            return
            
        items_to_remove = []
        for item in selected_items:
            # Check if it's our editable item
            if (hasattr(item, 'text_font') or hasattr(item, 'image_path')):
                items_to_remove.append(item)
        
        if items_to_remove:
            print(f"Deleting {len(items_to_remove)} selected items")
            
            for item in items_to_remove:
                try:
                    # Remove from scene
                    self.graphics_scene.removeItem(item)
                    
                    # Remove from elements list
                    if item in self.elements:
                        self.elements.remove(item)
                        
                except Exception as e:
                    print(f"Error deleting item: {e}")
            
            # Force scene update
            self.graphics_scene.update()
            print(f"Remaining elements: {len(self.elements)}") 