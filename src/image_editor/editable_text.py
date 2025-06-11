from PySide6.QtWidgets import (QGraphicsTextItem, QGraphicsItem, QTextEdit, 
                             QFontDialog, QColorDialog, QVBoxLayout, QHBoxLayout,
                             QPushButton, QWidget, QDialog, QLabel, QMenu)
from PySide6.QtCore import Qt, QRectF, Signal, QPointF
from PySide6.QtGui import QFont, QColor, QPainter, QPen, QBrush, QTextDocument, QTextCursor, QAction
from PIL import ImageFont, ImageDraw
import os
import platform
import glob

# Global font cache to avoid repeated searches
_font_cache = {}
_system_fonts_scanned = False

def scan_system_fonts():
    """Scan and cache system fonts once"""
    global _font_cache, _system_fonts_scanned
    
    if _system_fonts_scanned:
        return _font_cache
        
    try:
        system = platform.system().lower()
        font_dirs = []
        
        # Define font directories by system
        if system == "linux":
            font_dirs = [
                "/usr/share/fonts/",
                "/usr/local/share/fonts/",
                "~/.fonts/",
                "~/.local/share/fonts/"
            ]
        elif system == "darwin":  # macOS
            font_dirs = [
                "/System/Library/Fonts/",
                "/Library/Fonts/",
                "~/Library/Fonts/"
            ]
        elif system == "windows":
            font_dirs = [
                "C:/Windows/Fonts/",
                "C:/WINNT/Fonts/"
            ]
            
        # Expand user paths
        font_dirs = [os.path.expanduser(path) for path in font_dirs]
        
        # Scan all font files
        for font_dir in font_dirs:
            if not os.path.exists(font_dir):
                continue
                
            for ext in ["*.ttf", "*.TTF", "*.otf", "*.OTF"]:
                pattern = os.path.join(font_dir, "**", ext)
                for font_file in glob.glob(pattern, recursive=True):
                    font_name = os.path.basename(font_file).lower()
                    # Extract font family name from filename
                    base_name = os.path.splitext(font_name)[0]
                    
                    # Store multiple mappings for each font
                    for name_part in base_name.split('-')[0].split('_')[0].split():
                        if len(name_part) > 2:  # Avoid very short names
                            _font_cache[name_part.lower()] = font_file
                    
                    # Also store the full base name
                    _font_cache[base_name.replace('-', ' ').replace('_', ' ')] = font_file
        
        _system_fonts_scanned = True
        print(f"Scanned {len(_font_cache)} font mappings")
        
    except Exception as e:
        print(f"Error scanning system fonts: {e}")
        
    return _font_cache


class FontDialog(QDialog):
    def __init__(self, current_font, current_color, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Font Settings")
        self.setModal(True)
        self.result_font = current_font
        self.result_color = current_color
        
        layout = QVBoxLayout(self)
        
        # Font button
        font_btn = QPushButton(f"Font: {current_font.family()}, {current_font.pointSize()}pt")
        font_btn.clicked.connect(self.choose_font)
        layout.addWidget(font_btn)
        
        # Color button
        self.color_btn = QPushButton("Color")
        self.color_btn.setStyleSheet(f"background-color: {current_color.name()}")
        self.color_btn.clicked.connect(self.choose_color)
        layout.addWidget(self.color_btn)
        
        # OK/Cancel buttons
        button_layout = QHBoxLayout()
        ok_btn = QPushButton("OK")
        cancel_btn = QPushButton("Cancel")
        ok_btn.clicked.connect(self.accept)
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(ok_btn)
        button_layout.addWidget(cancel_btn)
        layout.addLayout(button_layout)
        
        self.font_btn = font_btn
        
    def choose_font(self):
        ok, font = QFontDialog.getFont(self.result_font, self)
        if ok:
            self.result_font = font
            self.font_btn.setText(f"Font: {font.family()}, {font.pointSize()}pt")
            
    def choose_color(self):
        color = QColorDialog.getColor(self.result_color, self)
        if color.isValid():
            self.result_color = color
            self.color_btn.setStyleSheet(f"background-color: {color.name()}")


class EditableTextItem(QGraphicsTextItem):
    def __init__(self, text="Sample Text"):
        super().__init__(text)
        self.setFlag(QGraphicsItem.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.ItemIsSelectable, True)
        self.setFlag(QGraphicsItem.ItemIsFocusable, True)
        
        # Default font and color
        self.text_font = QFont("Arial", 12)
        self.text_color = QColor("black")
        self.setFont(self.text_font)
        self.setDefaultTextColor(self.text_color)
        
        # Enable text interaction only when in edit mode
        self.setTextInteractionFlags(Qt.NoTextInteraction)
        self.is_editing = False
        
        # Draw selection handles
        self.show_handles = False
        
        # Store previous position for proper updates
        self.prev_pos = self.pos()
        
        # Text resizing
        self.resizing = False
        self.resize_handle_size = 12
        self.resize_handle_index = -1
        self.resize_start_pos = QPointF()
        self.resize_start_font_size = 12
        
        # Accept context menu events
        self.setAcceptedMouseButtons(Qt.LeftButton | Qt.RightButton)
        
    def itemChange(self, change, value):
        """Handle item changes to update display properly"""
        if change == QGraphicsItem.ItemPositionChange:
            # Update the previous position area
            if self.scene():
                old_rect = self.boundingRect().translated(self.pos())
                self.scene().update(old_rect)
                
        elif change == QGraphicsItem.ItemPositionHasChanged:
            # Update the new position area
            if self.scene():
                new_rect = self.boundingRect().translated(self.pos())
                self.scene().update(new_rect)
                
        return super().itemChange(change, value)

    def mouseDoubleClickEvent(self, event):
        """Enter edit mode on double click"""
        if not self.is_editing:
            self.enter_edit_mode()
        else:
            super().mouseDoubleClickEvent(event)
            
    def enter_edit_mode(self):
        """Enter text editing mode"""
        self.is_editing = True
        self.setTextInteractionFlags(Qt.TextEditorInteraction)
        self.setFocus()
        
        # Select all text for easy editing
        cursor = self.textCursor()
        cursor.select(QTextCursor.Document)
        self.setTextCursor(cursor)
        
        # Update display
        self.update()
        
    def focusOutEvent(self, event):
        """Exit edit mode when focus is lost"""
        if self.is_editing:
            self.is_editing = False
            self.setTextInteractionFlags(Qt.NoTextInteraction)
            self.clearFocus()
            # Force update of the entire item area
            self.update()
        super().focusOutEvent(event)
        
    def mousePressEvent(self, event):
        # Store current position for proper updating
        self.prev_pos = self.pos()
        
        if event.button() == Qt.RightButton and not self.is_editing:
            # Right click will show context menu, don't call super()
            return
        elif self.isSelected() and not self.is_editing and event.button() == Qt.LeftButton:
            # Check for resize handle clicks
            handle_rects = self.get_resize_handles()
            
            for i, handle_rect in enumerate(handle_rects):
                if handle_rect.contains(event.pos()):
                    self.resizing = True
                    self.resize_handle_index = i
                    self.resize_start_pos = event.pos()
                    self.resize_start_font_size = self.text_font.pointSize()
                    print(f"Started text resizing with handle {i}")
                    return
        else:
            super().mousePressEvent(event)
            
    def mouseMoveEvent(self, event):
        """Handle mouse move events with proper updates"""
        if self.resizing:
            self.resize_text(event.pos())
        elif self.flags() & QGraphicsItem.ItemIsMovable:
            # Update previous position area
            if self.scene():
                old_rect = self.boundingRect().translated(self.prev_pos)
                self.scene().update(old_rect)
                
            super().mouseMoveEvent(event)
            
            # Update current position
            self.prev_pos = self.pos()
        else:
            super().mouseMoveEvent(event)
        
    def mouseReleaseEvent(self, event):
        """Handle mouse release with final update"""
        if self.resizing:
            self.resizing = False
            print("Finished text resizing")
        
        super().mouseReleaseEvent(event)
        
        # Force update of the entire item area after moving/resizing
        if self.scene():
            rect = self.boundingRect().translated(self.pos())
            self.scene().update(rect)
            
    def show_font_dialog(self):
        """Show font configuration dialog"""
        # Ensure we have valid font and color objects
        if not isinstance(self.text_font, QFont):
            self.text_font = QFont("Arial", 12)
        if not isinstance(self.text_color, QColor):
            self.text_color = QColor("black")
            
        dialog = FontDialog(self.text_font, self.text_color, None)
        if dialog.exec() == QDialog.Accepted:
            self.text_font = dialog.result_font
            self.text_color = dialog.result_color
            self.setFont(self.text_font)
            self.setDefaultTextColor(self.text_color)
            # Force update after font change
            self.update()
            
    def get_resize_handles(self):
        """Get current resize handle rectangles for text"""
        if not self.isSelected() or self.is_editing:
            return []
            
        rect = super().boundingRect()  # Use original text bounding rect
        handle_size = self.resize_handle_size
        
        # Only corner handles for text (font size scaling)
        handles = [
            rect.topLeft(),
            rect.topRight(), 
            rect.bottomLeft(),
            rect.bottomRight()
        ]
        
        handle_rects = []
        for handle_pos in handles:
            handle_rect = QRectF(
                handle_pos.x() - handle_size/2,
                handle_pos.y() - handle_size/2,
                handle_size,
                handle_size
            )
            handle_rects.append(handle_rect)
        
        return handle_rects
            
    def boundingRect(self):
        """Return expanded bounding rectangle to include selection handles"""
        rect = super().boundingRect()
        
        if self.isSelected() and not self.is_editing:
            # Expand rect to include selection handles
            handle_size = self.resize_handle_size
            expanded_rect = rect.adjusted(-handle_size, -handle_size, handle_size, handle_size)
            return expanded_rect
            
        return rect
            
    def paint(self, painter, option, widget):
        """Custom paint method to show selection handles"""
        # Clear the background first
        if not self.is_editing:
            painter.fillRect(self.boundingRect(), QBrush(QColor(255, 255, 255, 0)))
            
        super().paint(painter, option, widget)
        
        if self.isSelected() and not self.is_editing:
            # Draw selection handles
            rect = super().boundingRect()  # Use the original text bounding rect
            pen = QPen(QColor("blue"), 2, Qt.DashLine)
            painter.setPen(pen)
            painter.drawRect(rect)
            
            # Draw resize handles
            handle_rects = self.get_resize_handles()
            brush = QBrush(QColor("blue"))
            painter.setBrush(brush)
            painter.setPen(QPen(QColor("blue")))
            
            for handle_rect in handle_rects:
                painter.drawRect(handle_rect)

    def find_system_font(self, font_family, font_size):
        """Find a system font file that matches the given font family"""
        try:
            # Ensure system fonts are scanned
            font_cache = scan_system_fonts()
            
            font_family_lower = font_family.lower()
            
            # Try exact match first
            if font_family_lower in font_cache:
                return ImageFont.truetype(font_cache[font_family_lower], font_size)
            
            # Try partial matches
            for cached_name, font_path in font_cache.items():
                if font_family_lower in cached_name or cached_name in font_family_lower:
                    return ImageFont.truetype(font_path, font_size)
            
            # Common font family fallbacks
            fallback_mappings = {
                "arial": ["dejavu", "liberation", "sans"],
                "helvetica": ["dejavu", "liberation", "arial", "sans"],
                "times": ["liberation", "serif", "times"],
                "courier": ["dejavu", "liberation", "mono", "courier"],
                "comic sans ms": ["comic"],
                "calibri": ["dejavu", "liberation", "sans"],
                "verdana": ["dejavu", "liberation", "sans"],
            }
            
            if font_family_lower in fallback_mappings:
                for fallback in fallback_mappings[font_family_lower]:
                    for cached_name, font_path in font_cache.items():
                        if fallback in cached_name:
                            return ImageFont.truetype(font_path, font_size)
            
            # Try the root directory font (Lucon.ttf)
            root_font = "Lucon.ttf"
            if os.path.exists(root_font):
                return ImageFont.truetype(root_font, font_size)
                
            # Final fallback to default font
            return ImageFont.load_default()
            
        except Exception as e:
            print(f"Error finding font {font_family}: {e}")
            return ImageFont.load_default()

    def render_to_pil(self, pil_image, draw):
        """Render this text item to a PIL image"""
        try:
            # Get text and position
            text = self.toPlainText()
            pos = self.pos()
            
            if not text.strip():  # Skip empty text
                return
            
            # Get font info from Qt font
            font_family = self.text_font.family()
            font_size = self.text_font.pointSize()
            
            # Ensure minimum font size
            font_size = max(font_size, 8)
            
            print(f"Rendering text '{text}' at ({int(pos.x())}, {int(pos.y())}) with font: {font_family}, size: {font_size}, Z: {self.zValue()}")
            
            # Find and load the appropriate PIL font
            pil_font = self.find_system_font(font_family, font_size)
            
            # Convert Qt color to RGB tuple
            color = (self.text_color.red(), self.text_color.green(), self.text_color.blue())
            
            # Draw text
            draw.text((int(pos.x()), int(pos.y())), text, fill=color, font=pil_font)
            
        except Exception as e:
            print(f"Error rendering text to PIL: {e}")
            # Fallback: draw with default font
            try:
                text = self.toPlainText()
                pos = self.pos()
                draw.text((int(pos.x()), int(pos.y())), text, fill=(0, 0, 0))
            except:
                pass

    def contextMenuEvent(self, event):
        """Show context menu with Z-order and font options"""
        if self.is_editing:
            # Let the text editor handle context menu when in edit mode
            super().contextMenuEvent(event)
            return
            
        menu = QMenu()
        
        # Font settings
        font_action = QAction("Font Settings...", menu)
        font_action.triggered.connect(self.show_font_dialog)
        menu.addAction(font_action)
        
        menu.addSeparator()
        
        # Z-order actions
        bring_to_front_action = QAction("Bring to Front", menu)
        bring_to_front_action.triggered.connect(self.bring_to_front)
        menu.addAction(bring_to_front_action)
        
        bring_forward_action = QAction("Bring Forward", menu)
        bring_forward_action.triggered.connect(self.bring_forward)
        menu.addAction(bring_forward_action)
        
        send_backward_action = QAction("Send Backward", menu)
        send_backward_action.triggered.connect(self.send_backward)
        menu.addAction(send_backward_action)
        
        send_to_back_action = QAction("Send to Back", menu)
        send_to_back_action.triggered.connect(self.send_to_back)
        menu.addAction(send_to_back_action)
        
        menu.addSeparator()
        
        # Delete action
        delete_action = QAction("Delete", menu)
        delete_action.triggered.connect(self.delete_item)
        delete_action.setShortcut("Delete")
        menu.addAction(delete_action)
        
        # Execute menu
        menu.exec(event.screenPos())

    def keyPressEvent(self, event):
        """Handle key press events for deletion and text editing"""
        if self.is_editing:
            # In edit mode, let the text editor handle all keys
            super().keyPressEvent(event)
        else:
            # In selection mode, handle delete keys
            if event.key() in (Qt.Key_Delete, Qt.Key_Backspace):
                self.delete_item()
                event.accept()
            else:
                super().keyPressEvent(event)

    def delete_item(self):
        """Delete this text item from the scene and canvas"""
        try:
            if self.scene():
                # Remove from scene
                self.scene().removeItem(self)
                
                # Find the canvas and remove from elements list
                canvas = None
                if self.scene().views():
                    view = self.scene().views()[0]
                    if hasattr(view, 'parent') and view.parent():
                        canvas_widget = view.parent()
                        while canvas_widget and not hasattr(canvas_widget, 'elements'):
                            canvas_widget = canvas_widget.parent()
                        if canvas_widget and hasattr(canvas_widget, 'elements'):
                            canvas = canvas_widget
                
                if canvas and self in canvas.elements:
                    canvas.elements.remove(self)
                    print(f"Text item deleted. Remaining elements: {len(canvas.elements)}")
                    
                # Force scene update
                if self.scene():
                    self.scene().update()
                    
        except Exception as e:
            print(f"Error deleting text item: {e}")

    def get_all_scene_items(self):
        """Get all movable items in the scene (excluding background)"""
        if not self.scene():
            return []
        
        items = []
        for item in self.scene().items():
            if hasattr(item, 'setFlag') and item != self:
                # Check if item is movable (text or image)
                if (isinstance(item, EditableTextItem) or 
                    hasattr(item, 'image_path')):  # EditableImageItem
                    items.append(item)
        return items

    def bring_to_front(self):
        """Bring this item to the front (highest Z value)"""
        if not self.scene():
            return
            
        all_items = self.get_all_scene_items()
        if not all_items:
            return
            
        # Find the highest Z value
        max_z = max(item.zValue() for item in all_items)
        self.setZValue(max_z + 1)
        self.update()

    def bring_forward(self):
        """Bring this item one level forward"""
        if not self.scene():
            return
            
        all_items = self.get_all_scene_items()
        if not all_items:
            return
            
        current_z = self.zValue()
        
        # Find the next higher Z value
        higher_z_values = [item.zValue() for item in all_items if item.zValue() > current_z]
        
        if higher_z_values:
            next_z = min(higher_z_values)
            # Swap Z values
            for item in all_items:
                if item.zValue() == next_z:
                    item.setZValue(current_z)
                    break
            self.setZValue(next_z)
        else:
            # Already at front, do nothing
            pass
            
        self.update()

    def send_backward(self):
        """Send this item one level backward"""
        if not self.scene():
            return
            
        all_items = self.get_all_scene_items()
        if not all_items:
            return
            
        current_z = self.zValue()
        
        # Find the next lower Z value
        lower_z_values = [item.zValue() for item in all_items if item.zValue() < current_z]
        
        if lower_z_values:
            next_z = max(lower_z_values)
            # Swap Z values
            for item in all_items:
                if item.zValue() == next_z:
                    item.setZValue(current_z)
                    break
            self.setZValue(next_z)
        else:
            # Already at back, do nothing
            pass
            
        self.update()

    def send_to_back(self):
        """Send this item to the back (lowest Z value)"""
        if not self.scene():
            return
            
        all_items = self.get_all_scene_items()
        if not all_items:
            return
            
        # Find the lowest Z value
        min_z = min(item.zValue() for item in all_items)
        self.setZValue(min_z - 1)
        self.update()

    def resize_text(self, new_pos):
        """Resize text by changing font size"""
        try:
            delta = new_pos - self.resize_start_pos
            
            # Calculate scale factor based on mouse movement
            scale_factor = 1.0 + (delta.x() + delta.y()) / 200.0  # Adjust sensitivity
            scale_factor = max(0.3, min(5.0, scale_factor))  # Limit scaling
            
            new_font_size = max(8, int(self.resize_start_font_size * scale_factor))
            
            # Update font size
            new_font = QFont(self.text_font)
            new_font.setPointSize(new_font_size)
            self.text_font = new_font
            self.setFont(self.text_font)
            
            # Force update
            self.update()
            
        except Exception as e:
            print(f"Error resizing text: {e}")

if __name__ == "__main__":
    import sys
    from PySide6.QtWidgets import QApplication

    app = QApplication(sys.argv)
    text_item = EditableTextItem()
    text_item.show()
    sys.exit(app.exec())

