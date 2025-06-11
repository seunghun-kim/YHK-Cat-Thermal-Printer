from PySide6.QtWidgets import QGraphicsPixmapItem, QGraphicsItem, QMenu
from PySide6.QtCore import Qt, QRectF, QPointF, QBuffer, QIODevice
from PySide6.QtGui import QPixmap, QPainter, QPen, QBrush, QColor, QTransform, QAction, QPainterPath
from PIL import Image
import os
import tempfile
import io


class EditableImageItem(QGraphicsPixmapItem):
    def __init__(self, image_path):
        super().__init__()
        
        self.image_path = image_path
        self.original_pixmap = None
        self.load_image(image_path)
        
        # Enable movement and selection
        self.setFlag(QGraphicsItem.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.ItemIsSelectable, True)
        
        # Store original size for scaling
        self.original_size = None
        if self.original_pixmap:
            self.original_size = self.original_pixmap.size()
            
        # Handle resize
        self.resize_handles = []
        self.resizing = False
        self.resize_handle_size = 12
        
        # Store previous position for proper updates
        self.prev_pos = self.pos()
        
        # Accept context menu events
        self.setAcceptedMouseButtons(Qt.LeftButton | Qt.RightButton)
        
    def load_image(self, image_path):
        """Load image from file path"""
        try:
            # Load with PIL first to handle various formats
            pil_image = Image.open(image_path)
            
            # Convert to RGB if necessary
            if pil_image.mode in ('RGBA', 'LA'):
                background = Image.new('RGB', pil_image.size, (255, 255, 255))
                if pil_image.mode == 'RGBA':
                    background.paste(pil_image, mask=pil_image.split()[-1])
                else:
                    background.paste(pil_image)
                pil_image = background
            elif pil_image.mode != 'RGB':
                pil_image = pil_image.convert('RGB')
            
            # Convert PIL image to QPixmap using in-memory buffer
            buffer = io.BytesIO()
            pil_image.save(buffer, format='PNG')
            buffer.seek(0)
            
            pixmap = QPixmap()
            pixmap.loadFromData(buffer.getvalue())
            
            # Scale down if too large (max 300px width/height)
            max_size = 300
            if pixmap.width() > max_size or pixmap.height() > max_size:
                pixmap = pixmap.scaled(max_size, max_size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            
            self.original_pixmap = pixmap
            self.setPixmap(pixmap)
                
        except Exception as e:
            print(f"Error loading image {image_path}: {e}")
            # Create a placeholder pixmap
            placeholder = QPixmap(100, 100)
            placeholder.fill(QColor("lightgray"))
            self.original_pixmap = placeholder
            self.setPixmap(placeholder)
            
    def paint(self, painter, option, widget):
        """Custom paint method to show selection handles"""
        super().paint(painter, option, widget)
        
        if self.isSelected():
            # Draw selection border
            rect = self.boundingRect()
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

    def mousePressEvent(self, event):
        """Handle mouse press for resizing"""
        # Store current position for proper updating
        self.prev_pos = self.pos()
        
        if event.button() == Qt.RightButton:
            # Right click will show context menu, don't call super()
            return
        
        if self.isSelected() and event.button() == Qt.LeftButton:
            # Get current handle rectangles
            handle_rects = self.get_resize_handles()
            
            # Check if clicking on a resize handle
            for i, handle_rect in enumerate(handle_rects):
                if handle_rect.contains(event.pos()):
                    self.resizing = True
                    self.resize_handle_index = i
                    self.resize_start_pos = event.pos()
                    self.resize_start_rect = self.boundingRect()
                    print(f"Started resizing with handle {i}")
                    return
        
        super().mousePressEvent(event)
        
    def mouseMoveEvent(self, event):
        """Handle mouse move for resizing"""
        if self.resizing:
            self.resize_item(event.pos())
        else:
            # Handle regular movement with proper updates
            if self.flags() & QGraphicsItem.ItemIsMovable:
                # Update previous position area
                if self.scene():
                    old_rect = self.boundingRect().translated(self.prev_pos)
                    self.scene().update(old_rect)
                    
            super().mouseMoveEvent(event)
            
            # Update current position
            self.prev_pos = self.pos()
            
    def mouseReleaseEvent(self, event):
        """Handle mouse release"""
        if self.resizing:
            self.resizing = False
            print("Finished resizing")
            # Update after resize
            if self.scene():
                rect = self.boundingRect().translated(self.pos())
                self.scene().update(rect)
        else:
            # Force update of the entire item area after moving
            if self.scene():
                rect = self.boundingRect().translated(self.pos())
                self.scene().update(rect)
                
        super().mouseReleaseEvent(event)
        
    def resize_item(self, new_pos):
        """Resize the item based on handle movement"""
        if not self.original_pixmap:
            return
            
        # Update the old area before resizing
        if self.scene():
            old_rect = self.boundingRect().translated(self.pos())
            self.scene().update(old_rect)
            
        delta = new_pos - self.resize_start_pos
        rect = self.resize_start_rect
        
        # Calculate new size based on which handle was dragged
        if self.resize_handle_index in [0, 1, 2, 3]:  # Corner handles
            # For corners, maintain aspect ratio - use the larger delta
            if abs(delta.x()) > abs(delta.y()):
                scale_factor = (rect.width() + delta.x()) / rect.width()
            else:
                scale_factor = (rect.height() + delta.y()) / rect.height()
                
            scale_factor = max(0.1, scale_factor)  # Minimum size
            new_size = self.original_size * scale_factor
            
        else:  # Side handles
            if self.resize_handle_index in [4, 5]:  # Top/bottom handles
                scale_factor = (rect.height() + delta.y()) / rect.height()
                scale_factor = max(0.1, scale_factor)
                new_size = self.original_size * scale_factor
            else:  # Left/right handles [6, 7]
                scale_factor = (rect.width() + delta.x()) / rect.width()
                scale_factor = max(0.1, scale_factor)
                new_size = self.original_size * scale_factor
        
        # Apply the scaling
        scaled_pixmap = self.original_pixmap.scaled(
            new_size, 
            Qt.KeepAspectRatio, 
            Qt.SmoothTransformation
        )
        self.setPixmap(scaled_pixmap)
        
        # Update the new area after resizing
        if self.scene():
            new_rect = self.boundingRect().translated(self.pos())
            self.scene().update(new_rect)

    def render_to_pil(self, pil_image, draw):
        """Render this image item to a PIL image"""
        try:
            # Get position and size
            pos = self.pos()
            pixmap = self.pixmap()
            
            print(f"Rendering image at ({int(pos.x())}, {int(pos.y())}) with Z: {self.zValue()}")
            
            if pixmap and not pixmap.isNull():
                # Convert QPixmap to PIL Image using in-memory buffer
                buffer = QBuffer()
                buffer.open(QIODevice.WriteOnly)
                pixmap.save(buffer, "PNG")
                
                pil_buffer = io.BytesIO(buffer.data())
                item_image = Image.open(pil_buffer)
                pil_image.paste(item_image, (int(pos.x()), int(pos.y())))
                    
        except Exception as e:
            print(f"Error rendering image to PIL: {e}")
            
    def boundingRect(self):
        """Return bounding rectangle for the image"""
        if self.pixmap():
            return QRectF(self.pixmap().rect())
        return QRectF(0, 0, 100, 100)

    def shape(self):
        """Return the shape for collision detection"""
        if self.isSelected():
            # Include handles in the shape when selected
            rect = self.boundingRect()
            handle_size = self.resize_handle_size
            expanded_rect = rect.adjusted(-handle_size, -handle_size, handle_size, handle_size)
            path = QPainterPath()
            path.addRect(expanded_rect)
            return path
        else:
            return super().shape()

    def get_resize_handles(self):
        """Get current resize handle rectangles"""
        if not self.isSelected():
            return []
            
        rect = self.boundingRect()
        handle_size = self.resize_handle_size
        
        handles = [
            rect.topLeft(),
            rect.topRight(), 
            rect.bottomLeft(),
            rect.bottomRight(),
            QPointF(rect.center().x(), rect.top()),  # Top center
            QPointF(rect.center().x(), rect.bottom()),  # Bottom center
            QPointF(rect.left(), rect.center().y()),  # Left center
            QPointF(rect.right(), rect.center().y())  # Right center
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

    def contextMenuEvent(self, event):
        """Show context menu with Z-order options"""
        menu = QMenu()
        
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
        """Handle key press events for deletion"""
        if event.key() in (Qt.Key_Delete, Qt.Key_Backspace):
            self.delete_item()
            event.accept()
        else:
            super().keyPressEvent(event)

    def delete_item(self):
        """Delete this image item from the scene and canvas"""
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
                    print(f"Image item deleted. Remaining elements: {len(canvas.elements)}")
                    
                # Force scene update
                if self.scene():
                    self.scene().update()
                    
        except Exception as e:
            print(f"Error deleting image item: {e}")

    def get_all_scene_items(self):
        """Get all movable items in the scene (excluding background)"""
        if not self.scene():
            return []
        
        items = []
        for item in self.scene().items():
            if hasattr(item, 'setFlag') and item != self:
                # Check if item is movable (text or image)
                if (hasattr(item, 'image_path') or  # EditableImageItem
                    hasattr(item, 'text_font')):    # EditableTextItem
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