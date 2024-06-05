import sys
import re
import logging
from PyQt5.QtCore import QRect, QRegularExpression, QUrl, Qt, QSettings, QSize
from PyQt5.QtWidgets import (QApplication, QColorDialog, QDialogButtonBox, QInputDialog, QListWidget, QMainWindow, QPlainTextEdit, QVBoxLayout, QPushButton, QWidget,
                             QTabWidget, QMenuBar, QAction, QFileDialog, QMessageBox, QDialog, QTableWidget,
                             QTableWidgetItem, QHBoxLayout, QCheckBox, QHeaderView, QComboBox, QLabel,
                             QLineEdit, QProgressBar, QGroupBox, QFormLayout, QGridLayout, QTextEdit, QSplitter,
                             QToolTip, QSpacerItem, QSizePolicy)
from PyQt5.QtGui import QIcon, QFont, QColor, QPainter, QPalette, QSyntaxHighlighter, QTextCharFormat, QTextCursor, QKeySequence, QTextFormat
from PyQt5.QtWebEngineWidgets import QWebEngineView

class DuplicateRemoverUserSettings:
    def __init__(self):
        self.last_opened_files = []
        self.window_size = QSize(800, 600)
        self.window_position = None
        self.duplicate_highlight_color = QColor("yellow")

    def load_settings(self, settings):
        self.last_opened_files = settings.value("last_opened_files", [])
        self.window_size = settings.value("window_size", QSize(800, 600))
        self.window_position = settings.value("window_position")
        self.duplicate_highlight_color = settings.value("duplicate_highlight_color", QColor("yellow"))

    def save_settings(self, settings):
        settings.setValue("last_opened_files", self.last_opened_files)
        settings.setValue("window_size", self.window_size)
        settings.setValue("window_position", self.window_position)
        settings.setValue("duplicate_highlight_color", self.duplicate_highlight_color)

class DuplicateRemoverLogger:
    def __init__(self, log_file):
        self.logger = logging.getLogger("TextEditorLogger")
        self.logger.setLevel(logging.DEBUG)

        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(logging.DEBUG)

        formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
        file_handler.setFormatter(formatter)

        self.logger.addHandler(file_handler)

    def log(self, level, message):
        self.logger.log(level, message)  

class DuplicateRemoverDuplicateConfirmDialog(QDialog):
    def __init__(self, duplicates, parent=None):
        super().__init__(parent)
        self.duplicates = duplicates
        self.selected_lines = []
        self.criteria = "exact"
        self.case_sensitive = True
        self.ignore_whitespace = False
        self.merge_duplicates = False
        self.initUI()

    def initUI(self):
        self.setWindowTitle("Confirm Duplicate Removal")
        layout = QVBoxLayout(self)

        criteria_layout = QHBoxLayout()
        criteria_label = QLabel("Duplicate Criteria:")
        criteria_layout.addWidget(criteria_label)

        self.criteria_combo = QComboBox()
        self.criteria_combo.addItems(["Exact Match", "Similar Text", "Regular Expression"])
        self.criteria_combo.currentTextChanged.connect(self.update_criteria)
        criteria_layout.addWidget(self.criteria_combo)

        self.case_check = QCheckBox("Case Sensitive")
        self.case_check.setChecked(self.case_sensitive)
        self.case_check.stateChanged.connect(self.update_case_sensitive)
        criteria_layout.addWidget(self.case_check)

        self.whitespace_check = QCheckBox("Ignore Whitespace")
        self.whitespace_check.setChecked(self.ignore_whitespace)
        self.whitespace_check.stateChanged.connect(self.update_ignore_whitespace)
        criteria_layout.addWidget(self.whitespace_check)

        layout.addLayout(criteria_layout)

        self.regex_input = QLineEdit()
        self.regex_input.setPlaceholderText("Enter regular expression")
        self.regex_input.setVisible(False)
        layout.addWidget(self.regex_input)

        self.tableWidget = QTableWidget()
        self.tableWidget.setColumnCount(2)
        self.tableWidget.setHorizontalHeaderLabels(['Select', 'Duplicate Line'])
        self.tableWidget.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)

        self.loadTableData()

        layout.addWidget(self.tableWidget)

        button_layout = QHBoxLayout()

        self.selectAllButton = QPushButton("Select All")
        self.selectAllButton.clicked.connect(self.selectAll)
        button_layout.addWidget(self.selectAllButton)

        self.deselectAllButton = QPushButton("Deselect All")
        self.deselectAllButton.clicked.connect(self.deselectAll)
        button_layout.addWidget(self.deselectAllButton)

        self.merge_check = QCheckBox("Merge Duplicates")
        self.merge_check.setChecked(self.merge_duplicates)
        self.merge_check.stateChanged.connect(self.update_merge_duplicates)
        button_layout.addWidget(self.merge_check)

        self.okButton = QPushButton("OK")
        self.okButton.clicked.connect(self.accept)
        button_layout.addWidget(self.okButton)

        self.cancelButton = QPushButton("Cancel")
        self.cancelButton.clicked.connect(self.reject)
        button_layout.addWidget(self.cancelButton)

        layout.addLayout(button_layout)

    def loadTableData(self):
        self.tableWidget.setRowCount(len(self.duplicates))
        for i, (line, _) in enumerate(self.duplicates):
            checkbox = QTableWidgetItem()
            checkbox.setCheckState(Qt.Checked)
            self.tableWidget.setItem(i, 0, checkbox)
            self.tableWidget.setItem(i, 1, QTableWidgetItem(line))

    def selectAll(self):
        for i in range(self.tableWidget.rowCount()):
            self.tableWidget.item(i, 0).setCheckState(Qt.Checked)

    def deselectAll(self):
        for i in range(self.tableWidget.rowCount()):
            self.tableWidget.item(i, 0).setCheckState(Qt.Unchecked)

    def update_criteria(self, text):
        self.criteria = text.lower().replace(" ", "_")
        self.regex_input.setVisible(self.criteria == "regular_expression")

    def update_case_sensitive(self, state):
        self.case_sensitive = state == Qt.Checked

    def update_ignore_whitespace(self, state):
        self.ignore_whitespace = state == Qt.Checked

    def update_merge_duplicates(self, state):
        self.merge_duplicates = state == Qt.Checked

    def accept(self):
        self.selected_lines = [self.tableWidget.item(i, 1).text() for i in range(self.tableWidget.rowCount()) if self.tableWidget.item(i, 0).checkState() == Qt.Checked]
        super().accept()

class DuplicateRemoverContextualDuplicateDialog(QDialog):
    def __init__(self, duplicates, parent=None):
        super().__init__(parent)
        self.duplicates = duplicates
        self.initUI()

    def initUI(self):
        self.setWindowTitle("Contextual Duplicate Analysis")
        layout = QVBoxLayout(self)

        self.tableWidget = QTableWidget()
        self.tableWidget.setColumnCount(3)
        self.tableWidget.setHorizontalHeaderLabels(['Duplicate Line', 'Previous Context', 'Next Context'])
        self.tableWidget.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)

        self.loadTableData()

        layout.addWidget(self.tableWidget)

        self.closeButton = QPushButton("Close")
        self.closeButton.clicked.connect(self.accept)
        layout.addWidget(self.closeButton)

    def loadTableData(self):
        self.tableWidget.setRowCount(len(self.duplicates))
        for i, (line, context) in enumerate(self.duplicates):
            self.tableWidget.setItem(i, 0, QTableWidgetItem(line))
            self.tableWidget.setItem(i, 1, QTableWidgetItem('\n'.join(context['previous'])))
            self.tableWidget.setItem(i, 2, QTableWidgetItem('\n'.join(context['next'])))

class DuplicateRemoverBatchRemovalWindow(QWidget):
    def __init__(self, parent=None):
        super(DuplicateRemoverBatchRemovalWindow, self).__init__(parent)
        self.setWindowTitle("Batch Duplicate Removal")
        self.setGeometry(100, 100, 600, 400)
        self.initUI()

    def initUI(self):
        layout = QVBoxLayout()

        self.fileListWidget = QListWidget()
        layout.addWidget(self.fileListWidget)

        button_layout = QHBoxLayout()

        self.addButton = QPushButton("Add Files")
        self.addButton.clicked.connect(self.add_files)
        button_layout.addWidget(self.addButton)

        self.removeButton = QPushButton("Remove Files")
        self.removeButton.clicked.connect(self.remove_files)
        button_layout.addWidget(self.removeButton)

        layout.addLayout(button_layout)

        self.progressBar = QProgressBar()
        self.progressBar.setRange(0, 100)
        layout.addWidget(self.progressBar)

        self.startButton = QPushButton("Start Batch Removal")
        self.startButton.clicked.connect(self.start_batch_removal)
        layout.addWidget(self.startButton)

        self.setLayout(layout)

    def add_files(self):
        file_paths, _ = QFileDialog.getOpenFileNames(self, "Select Files", "", "Text Files (*.txt);;Python Files (*.py);;C++ Files (*.cpp *.h);;Java Files (*.java)")
        self.fileListWidget.addItems(file_paths)

    def remove_files(self):
        current_item = self.fileListWidget.currentItem()
        if current_item:
            self.fileListWidget.takeItem(self.fileListWidget.row(current_item))

    def start_batch_removal(self):
        file_paths = [self.fileListWidget.item(i).text() for i in range(self.fileListWidget.count())]
        total_files = len(file_paths)
    
        duplicates_report = []
    
        for i, file_path in enumerate(file_paths):
            progress = (i + 1) / total_files * 100
            self.progressBar.setValue(progress)
        
            try:
                with open(file_path, 'r') as file:
                    lines = file.read().splitlines()
            
                duplicates = self.find_duplicates(lines)
                unique_lines = list(set(lines))
            
                if duplicates:
                    with open(file_path, 'w') as file:
                        file.write('\n'.join(unique_lines))
                
                    duplicates_report.extend([(duplicate, file_path, "Removed") for duplicate in duplicates])
                else:
                    duplicates_report.extend([(line, file_path, "No duplicates found") for line in unique_lines])
        
            except Exception as e:
                QMessageBox.critical(self, "Error", f"An error occurred while processing {file_path}: {str(e)}")
                return
    
        # Display the duplicate report
        report_window = DuplicateRemoverDuplicateReportWindow(duplicates_report, self)
        report_window.show()
    
        QMessageBox.information(self, "Batch Removal Complete", "Batch duplicate removal completed successfully.")

class DuplicateRemoverDuplicateReportWindow(QWidget):
    def __init__(self, duplicates, parent=None):
        super(DuplicateRemoverDuplicateReportWindow, self).__init__(parent)
        self.setWindowTitle("Duplicate Report")
        self.setGeometry(100, 100, 800, 600)
        self.duplicates = duplicates
        self.initUI()

    def initUI(self):
        layout = QVBoxLayout()

        self.reportTextEdit = QTextEdit()
        self.reportTextEdit.setReadOnly(True)
        layout.addWidget(self.reportTextEdit)

        button_layout = QHBoxLayout()

        self.exportButton = QPushButton("Export Report")
        self.exportButton.clicked.connect(self.export_report)
        button_layout.addWidget(self.exportButton)

        self.closeButton = QPushButton("Close")
        self.closeButton.clicked.connect(self.close)
        button_layout.addWidget(self.closeButton)

        layout.addLayout(button_layout)

        self.setLayout(layout)

        self.generate_report()

    def generate_report(self):
        report = "Duplicate Report\n\n"
        for i, (line, location, action) in enumerate(self.duplicates, start=1):
            report += f"Duplicate {i}:\n"
            report += f"Line: {line}\n"
            report += f"Location: {location}\n"
            report += f"Action: {action}\n\n"

        self.reportTextEdit.setPlainText(report)

    def export_report(self):
        file_path, _ = QFileDialog.getSaveFileName(self, "Export Report", "", "Text Files (*.txt)")
        if file_path:
            try:
                with open(file_path, 'w') as file:
                    file.write(self.reportTextEdit.toPlainText())
                QMessageBox.information(self, "Export Successful", "Duplicate report exported successfully.")
            except Exception as e:
                QMessageBox.critical(self, "Export Error", f"An error occurred while exporting the report: {str(e)}")

class DuplicateRemoverTabPage(QWidget):
    def __init__(self, logger, parent=None):
        super(DuplicateRemoverTabPage, self).__init__(parent)
        self.logger = logger        
        self.layout = QVBoxLayout(self)

        self.textEdit = CustomPlainTextEdit()
        self.textEdit.textChanged.connect(self.prevent_duplicates)
        self.textEdit.textChanged.connect(self.update_word_count)
        self.textEdit.textChanged.connect(self.update_line_count)
        self.layout.addWidget(self.textEdit)

        button_layout = QHBoxLayout()

        self.undoButton = QPushButton("Undo")
        self.undoButton.setShortcut(QKeySequence.Undo)
        self.undoButton.clicked.connect(self.textEdit.undo)
        button_layout.addWidget(self.undoButton)

        self.redoButton = QPushButton("Redo")
        self.redoButton.setShortcut(QKeySequence.Redo)
        self.redoButton.clicked.connect(self.textEdit.redo)
        button_layout.addWidget(self.redoButton)

        self.searchButton = QPushButton("Search")
        self.searchButton.clicked.connect(self.search_text)
        button_layout.addWidget(self.searchButton)

        self.replaceButton = QPushButton("Replace")
        self.replaceButton.clicked.connect(self.replace_text)
        button_layout.addWidget(self.replaceButton)

        self.bookmarkButton = QPushButton("Bookmark Duplicates")
        self.bookmarkButton.clicked.connect(self.bookmark_duplicates)
        button_layout.addWidget(self.bookmarkButton)

        self.contextButton = QPushButton("Show Duplicate Context")
        self.contextButton.clicked.connect(self.show_duplicate_context)
        button_layout.addWidget(self.contextButton)

        self.removeDuplicatesButton = QPushButton("Remove Duplicates")
        self.removeDuplicatesButton.clicked.connect(self.remove_duplicates)
        button_layout.addWidget(self.removeDuplicatesButton)

        # Add close button to the tab
        self.close_button = QPushButton("X")
        self.close_button.setFixedSize(20, 20)
        self.close_button.clicked.connect(self.close_tab)
        self.layout.addWidget(self.close_button, alignment=Qt.AlignTop | Qt.AlignRight)

        self.layout.addLayout(button_layout)

        self.file_path = None

        self.highlighter = PythonHighlighter(self.textEdit.document())
        self.highlighter.setDocument(None)

    def remove_duplicates(self):
        lines = self.get_text_lines()
        duplicates = self.find_duplicates(lines)
        if duplicates:
            dialog = DuplicateRemoverDuplicateConfirmDialog([(duplicate, None) for duplicate in duplicates], self)
            if dialog.exec_() == QDialog.Accepted:
                selected_duplicates = dialog.selected_lines
                unique_lines = [line for line in lines if line not in selected_duplicates]
                self.set_text_lines(unique_lines)
                self.logger.log(logging.INFO, f"Removed duplicates: {selected_duplicates}")
        else:
            QMessageBox.information(self, "No Duplicates", "No duplicate lines found.")

    def close_tab(self):
        parent = self.parent()
        while parent:
            if isinstance(parent, QTabWidget):
                parent.removeTab(parent.indexOf(self))
                break
            parent = parent.parent()

    def toggle_syntax_highlighting(self, enable):
        if enable:
            self.highlighter.setDocument(self.textEdit.document())
        else:
            self.highlighter.setDocument(None)

    def update_word_count(self):
        text = self.textEdit.toPlainText()
        word_count = len(text.split())
        main_window = self.get_main_window()
        if main_window:
            main_window.statusBar().showMessage(f"Word Count: {word_count}")

    def update_line_count(self):
        line_count = self.textEdit.blockCount()
        main_window = self.get_main_window()
        if main_window:
            main_window.statusBar().showMessage(f"Line Count: {line_count}")

    def get_main_window(self):
        parent = self.parentWidget()
        while parent:
            if isinstance(parent, DuplicateRemoverMainWindow):
                return parent
            parent = parent.parentWidget()
        return None

    def toggle_line_numbers(self, show_line_numbers):
        self.textEdit.lineNumberArea.setVisible(show_line_numbers)

    def update_line_number_area_width(self):
        self.textEdit.setViewportMargins(self.textEdit.line_number_area_width(), 0, 0, 0)

    def update_line_number_area(self, rect, dy):
        if dy:
            self.textEdit.lineNumberArea.scroll(0, dy)
        else:
            self.textEdit.lineNumberArea.update(0, rect.y(), self.textEdit.lineNumberArea.width(), rect.height())

        if rect.contains(self.textEdit.viewport().rect()):
            self.update_line_number_area_width()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        cr = self.textEdit.contentsRect()
        self.textEdit.lineNumberArea.setGeometry(QRect(cr.left(), cr.top(), self.textEdit.line_number_area_width(), cr.height()))

    def highlight_search_text(self, text):
        cursor = self.textEdit.textCursor()
        format = QTextCharFormat()
        format.setBackground(QColor("lightblue"))

        cursor.beginEditBlock()
        self.textEdit.moveCursor(QTextCursor.Start)
        while self.textEdit.find(text):
            cursor = self.textEdit.textCursor()
            cursor.mergeCharFormat(format)
        cursor.endEditBlock()

    def highlight_current_line(self):
        if self.textEdit.document().blockCount() == 1 and self.textEdit.toPlainText().strip() == "":
            return

        extraSelections = []

        if not self.textEdit.isReadOnly():
            selection = QTextEdit.ExtraSelection()

            lineColor = QColor(Qt.yellow).lighter(160)
            selection.format.setBackground(lineColor)
            selection.format.setProperty(QTextFormat.FullWidthSelection, True)
            selection.cursor = self.textEdit.textCursor()
            selection.cursor.clearSelection()
            extraSelections.append(selection)

        self.textEdit.setExtraSelections(extraSelections)

    def get_text_lines(self):
        return self.textEdit.toPlainText().split('\n')

    def set_text_lines(self, lines):
        self.textEdit.setPlainText('\n'.join(lines))

    def prevent_duplicates(self):
        lines = self.get_text_lines()
        duplicates = self.find_duplicates(lines)
        if duplicates:
            pass

    def bookmark_duplicates(self):
        lines = self.get_text_lines()
        duplicates = self.find_duplicates(lines)
        if not duplicates:
            return

        options, ok = QInputDialog.getItem(self, "Bookmark Options", "Choose the type of duplicates to bookmark:", ["Exact Duplicates", "Close Duplicates", "Lines that start the same"], 0, False)
        if not ok:
            return

        cursor = self.textEdit.textCursor()
        format = QTextCharFormat()
        format.setBackground(QColor("yellow"))

        if options == "Exact Duplicates":
            for line in duplicates:
                line_positions = [i for i, l in enumerate(lines) if l == line]
                for position in line_positions:
                    cursor.movePosition(QTextCursor.Start)
                    cursor.movePosition(QTextCursor.Down, QTextCursor.MoveAnchor, position)
                    cursor.movePosition(QTextCursor.EndOfLine, QTextCursor.KeepAnchor)
                    cursor.setCharFormat(format)

        elif options == "Close Duplicates":
            # Implement close duplicates logic here
            pass

        elif options == "Lines that start the same":
            starts = [line.split()[0] for line in lines if line.split()]
            for start in set(starts):
                start_positions = [i for i, l in enumerate(lines) if l.startswith(start)]
                for position in start_positions:
                    cursor.movePosition(QTextCursor.Start)
                    cursor.movePosition(QTextCursor.Down, QTextCursor.MoveAnchor, position)
                    cursor.movePosition(QTextCursor.EndOfLine, QTextCursor.KeepAnchor)
                    cursor.setCharFormat(format)

    def show_duplicate_context(self):
        lines = self.get_text_lines()
        duplicates_with_context = self.find_duplicates_with_context(lines)
        dialog = DuplicateRemoverContextualDuplicateDialog(duplicates_with_context, self)
        dialog.exec_()

    def find_duplicates(self, lines):
        duplicates = []
        seen = set()
        for line in lines:
            if line in seen:
                duplicates.append(line)
            else:
                seen.add(line)
        return duplicates

    def find_duplicates_with_context(self, lines, context_size=2):
        duplicates_with_context = []
        seen = set()
        for i, line in enumerate(lines):
            if line in seen:
                previous_context = lines[max(0, i - context_size):i]
                next_context = lines[i + 1:i + context_size + 1]
                duplicates_with_context.append((line, {'previous': previous_context, 'next': next_context}))
            else:
                seen.add(line)
        return duplicates_with_context

    def search_text(self):
        search_dialog = DuplicateRemoverSearchDialog(self)
        if search_dialog.exec_() == QDialog.Accepted:
            search_text = search_dialog.search_input.text()
            self.highlight_search_text(search_text)

    def replace_text(self):
        replace_dialog = DuplicateRemoverReplaceDialog(self)
        if replace_dialog.exec_() == QDialog.Accepted:
            search_text = replace_dialog.search_input.text()
            replace_text = replace_dialog.replace_input.text()
            use_regex = replace_dialog.regex_check.isChecked()
            self.replace_text(search_text, replace_text, use_regex)

    def sortLines(self, sort_type):
        lines = self.get_text_lines()
        if sort_type == 'line_size_asc':
            sorted_lines = sorted(lines, key=len)
        elif sort_type == 'line_size_desc':
            sorted_lines = sorted(lines, key=len, reverse=True)
        elif sort_type == 'alphabetical':
            sorted_lines = sorted(lines)
        self.set_text_lines(sorted_lines)
        
class PythonHighlighter(QSyntaxHighlighter):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.highlight_rules = []

        keyword_format = QTextCharFormat()
        keyword_format.setForeground(QColor("blue"))
        keyword_format.setFontWeight(QFont.Bold)
        keywords = ["and", "as", "assert", "break", "class", "continue", "def",
                    "del", "elif", "else", "except", "False", "finally", "for",
                    "from", "global", "if", "import", "in", "is", "lambda", "None",
                    "nonlocal", "not", "or", "pass", "raise", "return", "True",
                    "try", "while", "with", "yield"]
        self.highlight_rules.append((QRegularExpression(r"\b(" + "|".join(keywords) + r")\b"), keyword_format))

        # Add more highlighting rules for other syntax elements

    def highlightBlock(self, text):
        for pattern, format in self.highlight_rules:
            expression = QRegularExpression(pattern)
            match_iterator = expression.globalMatch(text)
            while match_iterator.hasNext():
                match = match_iterator.next()
                self.setFormat(match.capturedStart(), match.capturedLength(), format)

class CustomPlainTextEdit(QPlainTextEdit):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.lineNumberArea = LineNumberArea(self)
        self.blockCountChanged.connect(self.update_line_number_area_width)
        self.updateRequest.connect(self.update_line_number_area)
        self.cursorPositionChanged.connect(self.highlight_current_line)
        self.update_line_number_area_width()

    def line_number_area_width(self):
        digits = len(str(max(1, self.blockCount())))
        space = 3 + self.fontMetrics().width('9') * digits
        return space

    def update_line_number_area_width(self):
        self.setViewportMargins(self.line_number_area_width(), 0, 0, 0)

    def update_line_number_area(self, rect, dy):
        if dy:
            self.lineNumberArea.scroll(0, dy)
        else:
            self.lineNumberArea.update(0, rect.y(), self.lineNumberArea.width(), rect.height())

        if rect.contains(self.viewport().rect()):
            self.update_line_number_area_width()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        cr = self.contentsRect()
        self.lineNumberArea.setGeometry(QRect(cr.left(), cr.top(), self.line_number_area_width(), cr.height()))

    def highlight_current_line(self):
        if self.document().blockCount() == 1 and self.toPlainText().strip() == "":
            return

        extraSelections = []

        if not self.isReadOnly():
            selection = QTextEdit.ExtraSelection()

            lineColor = QColor(Qt.yellow).lighter(160)

            selection.format.setBackground(lineColor)
            selection.format.setProperty(QTextFormat.FullWidthSelection, True)
            selection.cursor = self.textCursor()
            selection.cursor.clearSelection()
            extraSelections.append(selection)

        self.setExtraSelections(extraSelections)

    def lineNumberAreaPaintEvent(self, event):
        painter = QPainter(self.lineNumberArea)
        painter.fillRect(event.rect(), Qt.lightGray)

        block = self.firstVisibleBlock()
        blockNumber = block.blockNumber()
        top = int(self.blockBoundingGeometry(block).translated(self.contentOffset()).top())
        bottom = top + int(self.blockBoundingRect(block).height())

        while block.isValid() and top <= event.rect().bottom():
            if block.isVisible() and bottom >= event.rect().top():
                number = str(blockNumber + 1)
                painter.setPen(Qt.black)
                painter.drawText(0, top, self.lineNumberArea.width(), self.fontMetrics().height(),
                                 Qt.AlignRight, number)

            block = block.next()
            top = bottom
            bottom = top + int(self.blockBoundingRect(block).height())
            blockNumber += 1

class LineNumberArea(QWidget):
    def __init__(self, editor):
        super().__init__(editor)
        self.editor = editor

    def sizeHint(self):
        return QSize(self.editor.line_number_area_width(), 0)

    def paintEvent(self, event):
        self.editor.lineNumberAreaPaintEvent(event)

class DuplicateRemoverSearchDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Search")
        self.initUI()

    def initUI(self):
        layout = QVBoxLayout(self)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Enter search text")
        layout.addWidget(self.search_input)

        button_layout = QHBoxLayout()

        self.searchButton = QPushButton("Search")
        self.searchButton.clicked.connect(self.accept)
        button_layout.addWidget(self.searchButton)

        self.cancelButton = QPushButton("Cancel")
        self.cancelButton.clicked.connect(self.reject)
        button_layout.addWidget(self.cancelButton)

        layout.addLayout(button_layout)

class DuplicateRemoverReplaceDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Replace")
        self.initUI()

    def initUI(self):
        layout = QVBoxLayout(self)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Enter search text")
        layout.addWidget(self.search_input)

        self.replace_input = QLineEdit()
        self.replace_input.setPlaceholderText("Enter replace text")
        layout.addWidget(self.replace_input)
        
        self.regex_check = QCheckBox("Use Regular Expression")
        layout.addWidget(self.regex_check)

        button_layout = QHBoxLayout()

        self.replaceButton = QPushButton("Replace")
        self.replaceButton.clicked.connect(self.accept)
        button_layout.addWidget(self.replaceButton)

        self.cancelButton = QPushButton("Cancel")
        self.cancelButton.clicked.connect(self.reject)
        button_layout.addWidget(self.cancelButton)

        layout.addLayout(button_layout)

class DuplicateRemoverMainWindow(QMainWindow):
    def __init__(self):
        super(DuplicateRemoverMainWindow, self).__init__()
        self.setWindowTitle("TSTP:Duplicate Deleter")
        self.setGeometry(100, 100, 800, 600)

        self.tabWidget = QTabWidget()
        self.setCentralWidget(self.tabWidget)

        self.user_settings = DuplicateRemoverUserSettings()
        self.logger = DuplicateRemoverLogger("app.log")

        self.load_settings()
        self.initUI()

    def initUI(self):
        self.menuBar().setNativeMenuBar(False)
        self.setupMenuBar()

        # Set up the status bar
        self.statusBar().showMessage("Ready")

        # Set up the progress bar in the status bar
        self.progressBar = QProgressBar()
        self.progressBar.setRange(0, 100)
        self.statusBar().addPermanentWidget(self.progressBar)

        # Set up the compare files feature
        self.compareFilesButton = QPushButton("Compare Files")
        self.compareFilesButton.clicked.connect(self.compare_files)
        self.statusBar().addPermanentWidget(self.compareFilesButton)

        # Set up the main layout
        main_layout = QVBoxLayout()
        central_widget = QWidget()
        central_widget.setLayout(main_layout)
        main_layout.addWidget(self.tabWidget)
        self.setCentralWidget(central_widget)

        # Set up tooltips and help texts
        self.setToolTip("Multiple File Editor")
        self.tabWidget.setToolTip("Edit multiple files in separate tabs")

        # Set up the tutorial
        self.tutorialWindow = DuplicateRemoverTutorialWindow(self)
        #self.tutorialWindow.show()

        # Restore the window size and position
        if self.user_settings.window_size:
            self.resize(self.user_settings.window_size)
        if self.user_settings.window_position:
            self.move(self.user_settings.window_position)

        # Open the last opened files
        for file_path in self.user_settings.last_opened_files:
            self.open_file(file_path)

    def setupMenuBar(self):
        menuBar = self.menuBar()
        fileMenu = menuBar.addMenu('File')

        newTabAction = QAction('New Tab', self)
        newTabAction.triggered.connect(self.newTab)
        fileMenu.addAction(newTabAction)

        openAction = QAction('Open', self)
        openAction.triggered.connect(self.openFile)
        fileMenu.addAction(openAction)

        saveAction = QAction('Save', self)
        saveAction.triggered.connect(self.saveFile)
        fileMenu.addAction(saveAction)

        saveAsAction = QAction('Save As', self)
        saveAsAction.triggered.connect(self.saveFileAs)
        fileMenu.addAction(saveAsAction)

        settingsAction = QAction('Settings', self)
        settingsAction.triggered.connect(self.openSettings)
        fileMenu.addAction(settingsAction)

        toggleDarkModeAction = QAction('Toggle Dark Mode', self)
        toggleDarkModeAction.triggered.connect(self.apply_dark_mode)
        fileMenu.addAction(toggleDarkModeAction)

        exitAction = QAction('Exit', self)
        exitAction.triggered.connect(self.close)
        fileMenu.addAction(exitAction)

        editMenu = menuBar.addMenu('Edit')

        removeDuplicatesAction = QAction('Remove Duplicates', self)
        removeDuplicatesAction.triggered.connect(self.removeDuplicates)
        editMenu.addAction(removeDuplicatesAction)

        mergeDuplicatesAction = QAction('Merge Duplicates', self)
        mergeDuplicatesAction.triggered.connect(self.mergeDuplicates)
        editMenu.addAction(mergeDuplicatesAction)

        sortMenu = editMenu.addMenu('Sort')

        sortAscLineSizeAction = QAction('Sort by Line Size (Ascending)', self)
        sortAscLineSizeAction.triggered.connect(lambda: self.sortLines('line_size_asc'))
        sortMenu.addAction(sortAscLineSizeAction)

        sortDescLineSizeAction = QAction('Sort by Line Size (Descending)', self)
        sortDescLineSizeAction.triggered.connect(lambda: self.sortLines('line_size_desc'))
        sortMenu.addAction(sortDescLineSizeAction)

        sortAlphabeticalAction = QAction('Sort Alphabetically', self)
        sortAlphabeticalAction.triggered.connect(lambda: self.sortLines('alphabetical'))
        sortMenu.addAction(sortAlphabeticalAction)

        goToLineAction = QAction('Go to Line', self)
        goToLineAction.triggered.connect(self.go_to_line)
        editMenu.addAction(goToLineAction)

        viewMenu = menuBar.addMenu('View')
        self.show_line_numbers_action = QAction('Show Line Numbers', self, checkable=True)
        self.show_line_numbers_action.triggered.connect(self.toggle_line_numbers)
        viewMenu.addAction(self.show_line_numbers_action)

        self.word_wrap_action = QAction('Word Wrap', self, checkable=True)
        self.word_wrap_action.triggered.connect(self.toggle_word_wrap)
        viewMenu.addAction(self.word_wrap_action)

        self.syntax_highlighting_action = QAction('Toggle Syntax Highlighting', self, checkable=True)
        self.syntax_highlighting_action.triggered.connect(self.toggle_syntax_highlighting)
        self.syntax_highlighting_action.setChecked(False)  # Disable by default
        viewMenu.addAction(self.syntax_highlighting_action)

        zoomInAction = QAction('Zoom In', self)
        zoomInAction.triggered.connect(self.zoom_in)
        viewMenu.addAction(zoomInAction)

        zoomOutAction = QAction('Zoom Out', self)
        zoomOutAction.triggered.connect(self.zoom_out)
        viewMenu.addAction(zoomOutAction)

        batchMenu = menuBar.addMenu('Batch')

        batchRemoveAction = QAction('Batch Duplicate Removal', self)
        batchRemoveAction.triggered.connect(self.batchRemoveDuplicates)
        batchMenu.addAction(batchRemoveAction)

        batchMergeAction = QAction('Batch Merge Files', self)
        batchMergeAction.triggered.connect(self.batchMergeFiles)
        batchMenu.addAction(batchMergeAction)

        helpMenu = menuBar.addMenu('Help')

        tutorialAction = QAction('Tutorial', self)
        tutorialAction.triggered.connect(self.showTutorial)
        helpMenu.addAction(tutorialAction)
        
    def apply_dark_mode(self):
        dark_stylesheet = """
        QWidget {
            background-color: #333333;
            color: #ffffff;
        }
        QPlainTextEdit {
            background-color: #1e1e1e;
            color: #dcdcdc;
        }
        QPushButton {
            background-color: #555555;
            border: 1px solid #666666;
            color: white;
        }
        QPushButton:hover {
            background-color: #777777;
        }
        QTabWidget::pane {
            border-top: 2px solid #555555;
        }
        QTabBar::tab {
            background-color: #555555;
            padding: 5px;
        }
        QTabBar::tab:selected {
            background: #333333;
            margin-bottom: -1px;
        }
        QMenuBar {
            background-color: #333333;
            color: #ffffff;
        }
        QMenuBar::item {
            background-color: #333333;
            color: #ffffff;
        }
        QMenuBar::item:selected {
            background-color: #555555;
        }
        QMenu {
            background-color: #333333;
            color: #ffffff;
        }
        QMenu::item:selected {
            background-color: #555555;
        }
        """
        self.setStyleSheet(dark_stylesheet)
        
    def toggle_syntax_highlighting(self):
        current_tab = self.tabWidget.currentWidget()
        if current_tab:
            current_tab.toggle_syntax_highlighting(self.syntax_highlighting_action.isChecked())

    def newTab(self, file_name="Untitled"):
        tab = DuplicateRemoverTabPage(self.logger)
        self.tabWidget.addTab(tab, file_name)
        self.tabWidget.setCurrentWidget(tab)

    def openFile(self):
        try:
            file_dialog = QFileDialog()
            file_dialog.setNameFilters(["UTF-8 (*.txt)", "UTF-16 (*.txt)", "ISO-8859-1 (*.txt)", "Windows-1252 (*.txt)", "All Files (*)"])
            file_dialog.selectNameFilter("UTF-8 (*.txt)")

            if file_dialog.exec_():
                selected_file = file_dialog.selectedFiles()[0]
                encoding = file_dialog.selectedNameFilter().split(" ")[0]

                with open(selected_file, 'r', encoding=encoding) as file:
                    content = file.read()

                current_tab = self.tabWidget.currentWidget()
                current_tab_index = self.tabWidget.currentIndex()
                file_name = selected_file.split('/')[-1]

                # If no tabs are open, open a new tab and load the file
                if self.tabWidget.count() == 0:
                    self.newTab(file_name)
                    current_tab = self.tabWidget.currentWidget()
                    current_tab_index = self.tabWidget.currentIndex()
                    current_tab.textEdit.setPlainText(content)
                    current_tab.file_path = selected_file
                # If the current tab is empty and named "Untitled", load the file in the current tab
                elif current_tab.textEdit.toPlainText() == "" and self.tabWidget.tabText(current_tab_index) == "Untitled":
                    current_tab.textEdit.setPlainText(content)
                    self.tabWidget.setTabText(current_tab_index, file_name)
                    current_tab.file_path = selected_file
                else:
                    # Open the file in a new tab
                    self.newTab(file_name)
                    new_tab = self.tabWidget.currentWidget()
                    new_tab.textEdit.setPlainText(content)
                    new_tab.file_path = selected_file

                # Ensure the new tab has the cursor at the start
                current_tab.textEdit.moveCursor(QTextCursor.Start)
                cursor = current_tab.textEdit.textCursor()
                cursor.movePosition(QTextCursor.Start)
                cursor.clearSelection()
                cursor.setCharFormat(QTextCharFormat())  # Clear any unwanted formatting
                self.logger.log(logging.INFO, f"Opened file: {selected_file} with encoding: {encoding}")

        except Exception as e:
            QMessageBox.critical(self, "Error", f"An error occurred while opening the file: {str(e)}")
            self.logger.log(logging.ERROR, f"Error opening file: {selected_file} - {str(e)}")

    def saveFile(self):
        current_tab = self.tabWidget.currentWidget()
        if current_tab and current_tab.file_path:
            self.save_file(current_tab.file_path)

    def saveFileAs(self):
        current_tab = self.tabWidget.currentWidget()
        if current_tab:
            file_path, _ = QFileDialog.getSaveFileName(self, "Save File As", "", "Text Files (*.txt);;Python Files (*.py);;C++ Files (*.cpp *.h);;Java Files (*.java)")
            if file_path:
                self.save_file(file_path)

    def save_file(self, file_path):
        try:
            file_dialog = QFileDialog()
            file_dialog.setNameFilters(["UTF-8 (*.txt)", "UTF-16 (*.txt)", "ISO-8859-1 (*.txt)", "Windows-1252 (*.txt)", "All Files (*)"])
            file_dialog.selectNameFilter("UTF-8 (*.txt)")
        
            if file_dialog.exec_():
                selected_file = file_dialog.selectedFiles()[0]
                encoding = file_dialog.selectedNameFilter().split(" ")[0]
            
                with open(selected_file, 'w', encoding=encoding) as file:
                    file.write(self.tabWidget.currentWidget().textEdit.toPlainText())
                self.tabWidget.setTabText(self.tabWidget.currentIndex(), selected_file.split('/')[-1])
                self.logger.log(logging.INFO, f"Saved file: {selected_file} with encoding: {encoding}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"An error occurred while saving the file: {str(e)}")
            self.logger.log(logging.ERROR, f"Error saving file: {file_path} - {str(e)}")
            
    def removeDuplicates(self):
        current_tab = self.tabWidget.currentWidget()
        if current_tab:
            lines = current_tab.get_text_lines()
            duplicates = current_tab.find_duplicates(lines)
            if duplicates:
                dialog = DuplicateRemoverDuplicateConfirmDialog([(duplicate, None) for duplicate in duplicates], self)
                if dialog.exec_() == QDialog.Accepted:
                    selected_duplicates = dialog.selected_lines
                    unique_lines = [line for line in lines if line not in selected_duplicates]
                    current_tab.set_text_lines(unique_lines)
                    self.logger.log(logging.INFO, f"Removed duplicates: {selected_duplicates}")
            else:
                QMessageBox.information(self, "No Duplicates", "No duplicate lines found.")
                
    def mergeDuplicates(self):
        current_tab = self.tabWidget.currentWidget()
        if current_tab:
            lines = current_tab.get_text_lines()
            duplicates = current_tab.find_duplicates(lines)
            if duplicates:
                dialog = DuplicateRemoverDuplicateConfirmDialog([(duplicate, None) for duplicate in duplicates], self)
                dialog.merge_check.setChecked(True)
                if dialog.exec_() == QDialog.Accepted:
                    selected_duplicates = dialog.selected_lines
                    merged_lines = self.merge_lines(lines, selected_duplicates)
                    current_tab.set_text_lines(merged_lines)
                    self.logger.log(logging.INFO, f"Merged duplicates: {selected_duplicates}")
            else:
                QMessageBox.information(self, "No Duplicates", "No duplicate lines found.")

    def merge_lines(self, lines, duplicates):
        merged_lines = []
        for line in lines:
            if line in duplicates:
                if line not in merged_lines:
                    merged_lines.append(line)
            else:
                merged_lines.append(line)
        return merged_lines
        
    def sortLines(self, sort_type):
        current_tab = self.tabWidget.currentWidget()
        if current_tab:
            current_tab.sortLines(sort_type)
            
    def go_to_line(self):
        current_tab = self.tabWidget.currentWidget()
        if current_tab:
            line_number, ok = QInputDialog.getInt(self, "Go to Line", "Enter line number:", min=1, max=current_tab.textEdit.blockCount())
            if ok:
                cursor = current_tab.textEdit.textCursor()
                cursor.movePosition(QTextCursor.Start)
                cursor.movePosition(QTextCursor.Down, QTextCursor.MoveAnchor, line_number - 1)
                current_tab.textEdit.setTextCursor(cursor)
                current_tab.textEdit.centerCursor()
                
    def toggle_line_numbers(self):
        current_tab = self.tabWidget.currentWidget()
        if current_tab:
            current_tab.toggle_line_numbers(self.show_line_numbers_action.isChecked())
            
    def toggle_word_wrap(self):
        current_tab = self.tabWidget.currentWidget()
        if current_tab:
            if self.word_wrap_action.isChecked():
                current_tab.textEdit.setLineWrapMode(QPlainTextEdit.WidgetWidth)
            else:
                current_tab.textEdit.setLineWrapMode(QPlainTextEdit.NoWrap)
                
    def zoom_in(self):
        current_tab = self.tabWidget.currentWidget()
        if current_tab:
            font = current_tab.textEdit.font()
            font.setPointSize(font.pointSize() + 1)
            current_tab.textEdit.setFont(font)

    def zoom_out(self):
        current_tab = self.tabWidget.currentWidget()
        if current_tab:
            font = current_tab.textEdit.font()
            font.setPointSize(max(1, font.pointSize() - 1))
            current_tab.textEdit.setFont(font)
            
    def batchRemoveDuplicates(self):
        batch_window = DuplicateRemoverBatchRemovalWindow(self)
        batch_window.show()

    def batchMergeFiles(self):
        file_paths, _ = QFileDialog.getOpenFileNames(self, "Select Files to Merge", "", "Text Files (*.txt);;Python Files (*.py);;C++ Files (*.cpp *.h);;Java Files (*.java)")
        if file_paths:
            merged_lines = []
            for file_path in file_paths:
                try:
                    with open(file_path, 'r') as file:
                        lines = file.read().splitlines()
                    merged_lines.extend(lines)
                except Exception as e:
                    QMessageBox.critical(self, "Error", f"An error occurred while reading file {file_path}: {str(e)}")
                    self.logger.log(logging.ERROR, f"Error reading file for merging: {file_path} - {str(e)}")
                    return

            merged_lines = list(set(merged_lines))  # Remove duplicates
            merged_file_path, _ = QFileDialog.getSaveFileName(self, "Save Merged File", "", "Text Files (*.txt);;Python Files (*.py);;C++ Files (*.cpp *.h);;Java Files (*.java)")
            if merged_file_path:
                try:
                    with open(merged_file_path, 'w') as file:
                        file.write('\n'.join(merged_lines))
                    self.logger.log(logging.INFO, f"Merged files: {file_paths} into {merged_file_path}")
                    QMessageBox.information(self, "Merge Complete", "Files merged successfully.")
                except Exception as e:
                    QMessageBox.critical(self, "Error", f"An error occurred while saving the merged file: {str(e)}")
                    self.logger.log(logging.ERROR, f"Error saving merged file: {merged_file_path} - {str(e)}")

    def compare_files(self):
        file_paths, _ = QFileDialog.getOpenFileNames(self, "Select Files to Compare", "", "Text Files (*.txt);;Python Files (*.py);;C++ Files (*.cpp *.h);;Java Files (*.java)")
        if len(file_paths) == 2:
            try:
                with open(file_paths[0], 'r') as file1, open(file_paths[1], 'r') as file2:
                    lines1 = file1.readlines()
                    lines2 = file2.readlines()

                diff_dialog = DuplicateRemoverFileDiffDialog(lines1, lines2, file_paths[0], file_paths[1], self)
                diff_dialog.exec_()
            except Exception as e:
                QMessageBox.critical(self, "Error", f"An error occurred while comparing the files: {str(e)}")
                self.logger.log(logging.ERROR, f"Error comparing files: {file_paths} - {str(e)}")
        else:
            QMessageBox.warning(self, "Invalid Selection", "Please select exactly two files for comparison.")

    def openSettings(self):
        settings_dialog = DuplicateRemoverSettingsDialog(self.user_settings, self)
        if settings_dialog.exec_() == QDialog.Accepted:
            self.user_settings = settings_dialog.user_settings
            self.logger.log(logging.INFO, "User settings updated")

    def showTutorial(self):
        self.tutorialWindow.show()

    def closeEvent(self, event):
        self.save_settings()
        event.accept()

    def load_settings(self):
        settings = QSettings("MyCompany", "MyApp")
        self.user_settings.load_settings(settings)

    def save_settings(self):
        settings = QSettings("MyCompany", "MyApp")
        self.user_settings.window_size = self.size()
        self.user_settings.window_position = self.pos()
        self.user_settings.last_opened_files = [self.tabWidget.widget(i).file_path for i in range(self.tabWidget.count()) if self.tabWidget.widget(i).file_path]
        self.user_settings.save_settings(settings)

    def replace_text(self, search_text, replace_text, use_regex=False):
        current_tab = self.tabWidget.currentWidget()
        if current_tab:
            if use_regex:
                current_tab.textEdit.setPlainText(re.sub(search_text, replace_text, current_tab.textEdit.toPlainText()))
            else:
                current_tab.textEdit.setPlainText(current_tab.textEdit.toPlainText().replace(search_text, replace_text))

    def replace_text_dialog(self):
        replace_dialog = DuplicateRemoverReplaceDialog(self)
        if replace_dialog.exec_() == QDialog.Accepted:
            search_text = replace_dialog.search_input.text()
            replace_text = replace_dialog.replace_input.text()
            use_regex = replace_dialog.regex_check.isChecked()
            self.replace_text(search_text, replace_text, use_regex)

class DuplicateRemoverFileDiffDialog(QDialog):
    def __init__(self, lines1, lines2, file1_path, file2_path, parent=None):
        super().__init__(parent)
        self.setWindowTitle("File Comparison")
        self.setGeometry(100, 100, 800, 600)
        self.initUI(lines1, lines2, file1_path, file2_path)

    def initUI(self, lines1, lines2, file1_path, file2_path):
        layout = QVBoxLayout(self)

        # Create text edits for displaying file contents
        text_edit1 = QPlainTextEdit()
        text_edit1.setPlainText(''.join(lines1))
        text_edit1.setReadOnly(True)

        text_edit2 = QPlainTextEdit()
        text_edit2.setPlainText(''.join(lines2))
        text_edit2.setReadOnly(True)

        # Create a splitter to hold the text edits side by side
        splitter = QSplitter()
        splitter.addWidget(text_edit1)
        splitter.addWidget(text_edit2)
        layout.addWidget(splitter)

        # Create a label to display the file paths
        file_label = QLabel(f"Comparing: {file1_path} <-> {file2_path}")
        layout.addWidget(file_label)

        # Create a button box with Close button
        button_box = QDialogButtonBox(QDialogButtonBox.Close)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

class DuplicateRemoverSettingsDialog(QDialog):
    def __init__(self, user_settings, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.user_settings = user_settings
        self.initUI()

    def initUI(self):
        layout = QVBoxLayout(self)

        # Create a form layout for settings fields
        form_layout = QFormLayout()

        # Add settings fields
        self.highlight_color_button = QPushButton()
        self.highlight_color_button.setStyleSheet(f"background-color: {self.user_settings.duplicate_highlight_color.name()}")
        self.highlight_color_button.clicked.connect(self.choose_highlight_color)
        form_layout.addRow("Duplicate Highlight Color:", self.highlight_color_button)

        layout.addLayout(form_layout)

        # Create a button box with OK and Cancel buttons
        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

    def choose_highlight_color(self):
        color = QColorDialog.getColor(self.user_settings.duplicate_highlight_color, self, "Choose Duplicate Highlight Color")
        if color.isValid():
            self.user_settings.duplicate_highlight_color = color
            self.highlight_color_button.setStyleSheet(f"background-color: {color.name()}")

    def accept(self):
        super().accept()
        
class DuplicateRemoverTutorialWindow(QDialog):
    def __init__(self, parent=None):
        super(DuplicateRemoverTutorialWindow, self).__init__(parent)
        self.setWindowTitle("Interactive Tutorial")
        self.setGeometry(100, 100, 800, 600)
        self.setWindowModality(Qt.ApplicationModal)

        self.layout = QVBoxLayout()

        self.webView = QWebEngineView()
        self.layout.addWidget(self.webView)

        self.navigation_layout = QHBoxLayout()
        self.back_button = QPushButton("Previous")
        self.back_button.clicked.connect(self.go_to_previous_page)
        self.navigation_layout.addWidget(self.back_button)

        self.forward_button = QPushButton("Next")
        self.forward_button.clicked.connect(self.go_to_next_page)
        self.navigation_layout.addWidget(self.forward_button)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.navigation_layout.addWidget(self.progress_bar)

        self.start_button = QPushButton("Start Editing")
        self.start_button.clicked.connect(self.close)
        self.navigation_layout.addWidget(self.start_button)

        self.layout.addLayout(self.navigation_layout)
        self.setLayout(self.layout)

        self.current_page_index = 0
        self.tutorial_pages = [
            self.create_welcome_page(),
            self.create_opening_files_page(),
            self.create_editing_files_page(),
            self.create_saving_files_page(),
            self.create_removing_duplicates_page(),
            self.create_sorting_and_merging_page(),
            self.create_batch_operations_page(),
            self.create_additional_features_page(),
        ]

        self.load_tutorial_page(self.current_page_index)

    def create_welcome_page(self):
        return """
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {
                    font-family: 'Arial', sans-serif;
                    margin: 20px;
                    padding: 20px;
                    line-height: 1.6;
                    background-color: #f4f4f4;
                    color: #333;
                }
                h1 {
                    color: #026be4;
                    text-align: center;
                }
                p {
                    margin: 10px 0;
                }
                .button {
                    background-color: #4CAF50;
                    border: none;
                    color: white;
                    padding: 15px 32px;
                    text-align: center;
                    text-decoration: none;
                    display: inline-block;
                    font-size: 16px;
                    margin: 4px 2px;
                    cursor: pointer;
                    border-radius: 5px;
                }
            </style>
        </head>
        <body>
            <h1>Welcome to the TSTP:Duplicate Deleter Tutorial</h1>
            <p>In this interactive tutorial, you will learn how to use the key features of the TSTP:Duplicate Deleter application.</p>
            <p>Let's get started!</p>
        </body>
        </html>
        """

    def create_opening_files_page(self):
        return """
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {
                    font-family: 'Arial', sans-serif;
                    margin: 20px;
                    padding: 20px;
                    line-height: 1.6;
                    background-color: #f4f4f4;
                    color: #333;
                }
                h2 {
                    color: #0294a5;
                }
                p {
                    margin: 10px 0;
                }
                ol {
                    padding: 20px;
                }
                li {
                    margin: 10px 0;
                    font-size: 16px;
                }
                code {
                    font-family: 'Courier New', monospace;
                    background-color: #eaeaea;
                    padding: 2px 5px;
                    border-radius: 3px;
                }
                .button {
                    background-color: #4CAF50;
                    border: none;
                    color: white;
                    padding: 15px 32px;
                    text-align: center;
                    text-decoration: none;
                    display: inline-block;
                    font-size: 16px;
                    margin: 4px 2px;
                    cursor: pointer;
                    border-radius: 5px;
                }
            </style>
        </head>
        <body>
            <h2>Opening Files</h2>
            <p>To open a file, follow these steps:</p>
            <ol>
                <li>Click on the <code>File</code> menu in the top-left corner.</li>
                <li>Select the <code>Open</code> option.</li>
                <li>In the file dialog, navigate to the file you want to open and click <code>Open</code>.</li>
            </ol>
            <p>Each file you open will be displayed in a new tab.</p>
        </body>
        </html>
        """

    def create_editing_files_page(self):
        return """
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {
                    font-family: 'Arial', sans-serif;
                    margin: 20px;
                    padding: 20px;
                    line-height: 1.6;
                    background-color: #f4f4f4;
                    color: #333;
                }
                h2 {
                    color: #0294a5;
                }
                p {
                    margin: 10px 0;
                }
                .button {
                    background-color: #4CAF50;
                    border: none;
                    color: white;
                    padding: 15px 32px;
                    text-align: center;
                    text-decoration: none;
                    display: inline-block;
                    font-size: 16px;
                    margin: 4px 2px;
                    cursor: pointer;
                    border-radius: 5px;
                }
            </style>
        </head>
        <body>
            <h2>Editing Files</h2>
            <p>To edit the contents of a file, simply make changes directly in the text editor provided in each tab.</p>
            <p>You can use the standard keyboard shortcuts for common editing operations, such as:</p>
            <ul>
                <li><code>Ctrl+Z</code> to undo your changes</li>
                <li><code>Ctrl+Y</code> to redo your changes</li>
                <li><code>Ctrl+F</code> to search for text within the file</li>
                <li><code>Ctrl+H</code> to replace text within the file</li>
            </ul>
        </body>
        </html>
        """

    def create_saving_files_page(self):
        return """
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {
                    font-family: 'Arial', sans-serif;
                    margin: 20px;
                    padding: 20px;
                    line-height: 1.6;
                    background-color: #f4f4f4;
                    color: #333;
                }
                h2 {
                    color: #0294a5;
                }
                p {
                    margin: 10px 0;
                }
                ol {
                    padding: 20px;
                }
                li {
                    margin: 10px 0;
                    font-size: 16px;
                }
                code {
                    font-family: 'Courier New', monospace;
                    background-color: #eaeaea;
                    padding: 2px 5px;
                    border-radius: 3px;
                }
                .button {
                    background-color: #4CAF50;
                    border: none;
                    color: white;
                    padding: 15px 32px;
                    text-align: center;
                    text-decoration: none;
                    display: inline-block;
                    font-size: 16px;
                    margin: 4px 2px;
                    cursor: pointer;
                    border-radius: 5px;
                }
            </style>
        </head>
        <body>
            <h2>Saving Files</h2>
            <p>To save your changes, you can use the following options:</p>
            <ol>
                <li>Click on the <code>Save</code> button in the toolbar to save the current file.</li>
                <li>Go to the <code>File</code> menu and select <code>Save</code> to save the current file.</li>
                <li>To save a file with a new name or in a different location, go to the <code>File</code> menu and select <code>Save As</code>.</li>
            </ol>
        </body>
        </html>
        """

    def create_removing_duplicates_page(self):
        return """
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {
                    font-family: 'Arial', sans-serif;
                    margin: 20px;
                    padding: 20px;
                    line-height: 1.6;
                    background-color: #f4f4f4;
                    color: #333;
                }
                h2 {
                    color: #0294a5;
                }
                p {
                    margin: 10px 0;
                }
                ol {
                    padding: 20px;
                }
                li {
                    margin: 10px 0;
                    font-size: 16px;
                }
                code {
                    font-family: 'Courier New', monospace;
                    background-color: #eaeaea;
                    padding: 2px 5px;
                    border-radius: 3px;
                }
                .button {
                    background-color: #4CAF50;
                    border: none;
                    color: white;
                    padding: 15px 32px;
                    text-align: center;
                    text-decoration: none;
                    display: inline-block;
                    font-size: 16px;
                    margin: 4px 2px;
                    cursor: pointer;
                    border-radius: 5px;
                }
            </style>
        </head>
        <body>
            <h2>Removing Duplicates</h2>
            <p>To remove duplicate lines from your file, follow these steps:</p>
            <ol>
                <li>Go to the <code>Edit</code> menu and select the <code>Remove Duplicates</code> option.</li>
                <li>A dialog will appear, allowing you to choose which duplicate lines to remove. You can select the specific lines you want to remove or choose to remove all duplicates.</li>
                <li>Once you've made your selection, click <code>OK</code> to apply the changes.</li>
            </ol>
        </body>
        </html>
        """

    def create_sorting_and_merging_page(self):
        return """
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {
                    font-family: 'Arial', sans-serif;
                    margin: 20px;
                    padding: 20px;
                    line-height: 1.6;
                    background-color: #f4f4f4;
                    color: #333;
                }
                h2 {
                    color: #0294a5;
                }
                p {
                    margin: 10px 0;
                }
                ol {
                    padding: 20px;
                }
                li {
                    margin: 10px 0;
                    font-size: 16px;
                }
                code {
                    font-family: 'Courier New', monospace;
                    background-color: #eaeaea;
                    padding: 2px 5px;
                    border-radius: 3px;
                }
                .button {
                    background-color: #4CAF50;
                    border: none;
                    color: white;
                    padding: 15px 32px;
                    text-align: center;
                    text-decoration: none;
                    display: inline-block;
                    font-size: 16px;
                    margin: 4px 2px;
                    cursor: pointer;
                    border-radius: 5px;
                }
            </style>
        </head>
        <body>
            <h2>Sorting and Merging</h2>
            <p>The TSTP:Duplicate Deleter application also provides the following features:</p>
            <ol>
                <li>Sorting: You can sort the lines in your file in ascending or descending order. Go to the <code>Edit</code> menu and select either <code>Sort Ascending</code> or <code>Sort Descending</code>.</li>
                <li>Merging: If you have duplicate lines that you want to keep, you can merge them into a single line. Go to the <code>Edit</code> menu and select <code>Merge Duplicates</code>.</li>
            </ol>
        </body>
        </html>
        """
    def create_batch_operations_page(self):
        return """
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {
                    font-family: 'Arial', sans-serif;
                    margin: 20px;
                    padding: 20px;
                    line-height: 1.6;
                    background-color: #f4f4f4;
                    color: #333;
                }
                h2 {
                    color: #0294a5;
                }
                p {
                    margin: 10px 0;
                }
                ol {
                    padding: 20px;
                }
                li {
                    margin: 10px 0;
                    font-size: 16px;
                }
                code {
                    font-family: 'Courier New', monospace;
                    background-color: #eaeaea;
                    padding: 2px 5px;
                    border-radius: 3px;
                }
                .button {
                    background-color: #4CAF50;
                    border: none;
                    color: white;
                    padding: 15px 32px;
                    text-align: center;
                    text-decoration: none;
                    display: inline-block;
                    font-size: 16px;
                    margin: 4px 2px;
                    cursor: pointer;
                    border-radius: 5px;
                }
            </style>
        </head>
        <body>
            <h2>Batch Operations</h2>
            <p>The TSTP:Duplicate Deleter application also supports batch operations, allowing you to process multiple files at once.</p>
            <ol>
                <li>
                    <strong>Batch Duplicate Removal:</strong>
                    <ul>
                        <li>Go to the <code>Batch</code> menu and select <code>Batch Duplicate Removal</code>.</li>
                        <li>In the Batch Duplicate Removal window, click the <code>Add Files</code> button to select the files you want to process.</li>
                        <li>Once you've added the files, click the <code>Start Batch Removal</code> button to remove duplicates from all the files.</li>
                    </ul>
                </li>
                <li>
                    <strong>Batch File Merging:</strong>
                    <ul>
                        <li>Go to the <code>Batch</code> menu and select <code>Batch Merge Files</code>.</li>
                        <li>In the file dialog, select the files you want to merge.</li>
                        <li>The application will combine the contents of all the selected files into a single file, which you can then save.</li>
                    </ul>
                </li>
            </ol>
        </body>
        </html>
        """

    def create_additional_features_page(self):
        return """
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {
                    font-family: 'Arial', sans-serif;
                    margin: 20px;
                    padding: 20px;
                    line-height: 1.6;
                    background-color: #f4f4f4;
                    color: #333;
                }
                h2 {
                    color: #0294a5;
                }
                p {
                    margin: 10px 0;
                }
                ul {
                    padding: 20px;
                }
                li {
                    margin: 10px 0;
                    font-size: 16px;
                }
                code {
                    font-family: 'Courier New', monospace;
                    background-color: #eaeaea;
                    padding: 2px 5px;
                    border-radius: 3px;
                }
                .button {
                    background-color: #4CAF50;
                    border: none;
                    color: white;
                    padding: 15px 32px;
                    text-align: center;
                    text-decoration: none;
                    display: inline-block;
                    font-size: 16px;
                    margin: 4px 2px;
                    cursor: pointer;
                    border-radius: 5px;
                }
            </style>
        </head>
        <body>
            <h2>Additional Features</h2>
            <p>The TSTP:Duplicate Deleter application also includes the following additional features:</p>
            <ul>
                <li>
                    <strong>File Comparison:</strong>
                    <ul>
                        <li>You can compare the contents of two files side-by-side.</li>
                        <li>Go to the <code>File</code> menu and select <code>Compare Files</code>.</li>
                    </ul>
                </li>
                <li>
                    <strong>Dark Mode:</strong>
                    <ul>
                        <li>The application supports a dark mode theme to reduce eye strain.</li>
                        <li>Toggle dark mode by going to the <code>File</code> menu and selecting <code>Toggle Dark Mode</code>.</li>
                    </ul>
                </li>
            </ul>
            <button class="button previous-button">Previous</button>
            <button class="button start-button">Start Editing</button>
        </body>
        </html>
        """

    def load_tutorial_page(self, index):
        self.webView.setHtml(self.tutorial_pages[index])
        self.progress_bar.setValue(int((index + 1) / len(self.tutorial_pages) * 100))

    def go_to_previous_page(self):
        if self.current_page_index > 0:
            self.current_page_index -= 1
            self.load_tutorial_page(self.current_page_index)

    def go_to_next_page(self):
        if self.current_page_index < len(self.tutorial_pages) - 1:
            self.current_page_index += 1
            self.load_tutorial_page(self.current_page_index)      

def main():
    app = QApplication(sys.argv)
    main_window = DuplicateRemoverMainWindow()
    main_window.show()
    sys.exit(app.exec_())

if __name__ == '__main__':
    main()
    
