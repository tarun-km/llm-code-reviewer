import sys
import subprocess, tempfile, os
import markdown
import ollama

from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QTextBrowser,
                             QPlainTextEdit, QPushButton, QComboBox, QLabel,
                             QVBoxLayout, QHBoxLayout, QSplitter)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QPalette, QColor, QFont

# Helper functions for code execution
def run_python(code):
    try:
        result = subprocess.run(["python", "-c", code],
                                capture_output=True, text=True)
        return result.stdout if result.stdout else result.stderr
    except Exception as e:
        return f"Execution Error: {str(e)}"

def run_c(code):
    with tempfile.NamedTemporaryFile(delete=False, suffix=".c", mode="w", encoding="utf-8") as src_file:
        src_file.write(code)
        src_file_name = src_file.name
    exe_file = src_file_name[:-2]  # remove .c extension
    compile_proc = subprocess.run(["gcc", src_file_name, "-o", exe_file],
                                  capture_output=True, text=True)
    if compile_proc.returncode != 0:
        out = "Compilation Error:\n" + compile_proc.stderr
    else:
        run_proc = subprocess.run([exe_file], capture_output=True, text=True)
        out = run_proc.stdout if run_proc.stdout else run_proc.stderr
    os.remove(src_file_name)
    if os.path.exists(exe_file):
        os.remove(exe_file)
    return out

def run_cpp(code):
    with tempfile.NamedTemporaryFile(delete=False, suffix=".cpp", mode="w", encoding="utf-8") as src_file:
        src_file.write(code)
        src_file_name = src_file.name
    exe_file = src_file_name[:-4]  # remove .cpp extension
    compile_proc = subprocess.run(["g++", src_file_name, "-o", exe_file],
                                  capture_output=True, text=True)
    if compile_proc.returncode != 0:
        out = "Compilation Error:\n" + compile_proc.stderr
    else:
        run_proc = subprocess.run([exe_file], capture_output=True, text=True)
        out = run_proc.stdout if run_proc.stdout else run_proc.stderr
    os.remove(src_file_name)
    if os.path.exists(exe_file):
        os.remove(exe_file)
    return out

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("AI-Powered Code Reviewer")
        self.resize(1200, 700)

        # Use QSplitter to separate LLM response (left) from code editor (right)
        splitter = QSplitter(Qt.Horizontal)
        self.setCentralWidget(splitter)

        # Left pane: LLM response using QTextBrowser
        self.llmBrowser = QTextBrowser()
        self.llmBrowser.setStyleSheet("""
            QTextBrowser { 
                background-color: #121212; 
                color: #ffffff; 
                padding: 15px; 
                border: none;
            }
        """)
        self.llmBrowser.setFont(QFont("Arial", 12))
        self.llmBrowser.setHtml(
            "<div style='background-color:#121212; color:#ffffff; padding:15px;'>"
            "LLM response will appear here."
            "</div>"
        )
        splitter.addWidget(self.llmBrowser)
        splitter.setStretchFactor(0, 1)

        # Right pane: Contains toolbar, code editor, and output area
        rightWidget = QWidget()
        rightLayout = QVBoxLayout(rightWidget)
        rightLayout.setContentsMargins(10, 10, 10, 10)
        rightLayout.setSpacing(10)
        splitter.addWidget(rightWidget)
        splitter.setStretchFactor(1, 2)

        # Toolbar: language selection and buttons
        toolbar = QHBoxLayout()
        toolbar.setSpacing(10)
        self.langCombo = QComboBox()
        self.langCombo.addItems(["python", "c", "c++"])
        self.langCombo.setStyleSheet("""
            QComboBox { 
                background-color: #2b2b2b; 
                color: white; 
                padding: 5px;
                border: 1px solid #444;
                border-radius: 4px;
            }
        """)
        toolbar.addWidget(QLabel("Language:"))
        toolbar.addWidget(self.langCombo)

        self.analyzeBtn = QPushButton("Analyze Code")
        self.analyzeBtn.clicked.connect(self.analyze_code)
        self.analyzeBtn.setStyleSheet("""
            QPushButton {
                background-color: #2b2b2b;
                color: white;
                padding: 5px 10px;
                border: 1px solid #444;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #3c3c3c;
            }
        """)
        toolbar.addWidget(self.analyzeBtn)

        self.runBtn = QPushButton("Run Code")
        self.runBtn.clicked.connect(self.run_code)
        self.runBtn.setStyleSheet(self.analyzeBtn.styleSheet())
        toolbar.addWidget(self.runBtn)

        self.clearBtn = QPushButton("Clear All")
        self.clearBtn.clicked.connect(self.clear_all)
        self.clearBtn.setStyleSheet(self.analyzeBtn.styleSheet())
        toolbar.addWidget(self.clearBtn)

        toolbar.addStretch()
        rightLayout.addLayout(toolbar)

        # Code editor
        self.codeEditor = QPlainTextEdit()
        self.codeEditor.setStyleSheet("""
            QPlainTextEdit { 
                background-color: #121212; 
                color: white; 
                font-family: Courier; 
                font-size: 12pt; 
                padding: 15px;
                border: 1px solid #444;
                border-radius: 4px;
            }
        """)
        self.codeEditor.setFont(QFont("Courier", 12))
        rightLayout.addWidget(self.codeEditor, stretch=3)

        # Output area
        self.outputArea = QPlainTextEdit()
        self.outputArea.setReadOnly(True)
        self.outputArea.setStyleSheet("""
            QPlainTextEdit { 
                background-color: #121212; 
                color: white; 
                font-family: Courier; 
                font-size: 12pt; 
                padding: 15px;
                border: 1px solid #444;
                border-radius: 4px;
            }
        """)
        self.outputArea.setFont(QFont("Courier", 12))
        rightLayout.addWidget(self.outputArea, stretch=1)

    def analyze_code(self):
        code = self.codeEditor.toPlainText().strip()
        # Show a loading message
        self.llmBrowser.setHtml(
            "<div style='background-color:#121212; color:#ffffff; padding:15px;'>"
            "<em>Analyzing code, please wait...</em></div>"
        )
        if not code:
            self.llmBrowser.setHtml(
                "<div style='background-color:#121212; color:#ffffff; padding:15px;'>"
                "<strong>Error:</strong> No code to analyze.</div>"
            )
            return

        lang = self.langCombo.currentText()
        prompt = f"Review and optimize this {lang} code:\n\n{code}"
        try:
            response = ollama.chat(
                model="deepseek-coder-v2:latest",
                messages=[{"role": "user", "content": prompt}]
            )
            md_response = response['message']['content']
        except Exception as e:
            self.llmBrowser.setHtml(
                f"<div style='background-color:#121212; color:#ffffff; padding:15px;'>"
                f"<strong>Error during API call:</strong> {e}</div>"
            )
            return

        # Convert Markdown to HTML
        html_body = markdown.markdown(md_response, extensions=['fenced_code', 'codehilite'])
        html_content = (
            "<div style='background-color:#121212; color:#ffffff; font-family:Arial, sans-serif; padding:15px;'>"
            f"{html_body}"
            "</div>"
        )
        self.llmBrowser.setHtml(html_content)

    def run_code(self):
        code = self.codeEditor.toPlainText().strip()
        self.outputArea.clear()
        if not code:
            self.outputArea.setPlainText("Error: No code to execute.")
            return

        lang = self.langCombo.currentText()
        if lang == "python":
            output = run_python(code)
        elif lang == "c":
            output = run_c(code)
        elif lang == "c++":
            output = run_cpp(code)
        else:
            output = "Unsupported language."

        self.outputArea.setPlainText(output)

    def clear_all(self):
        self.codeEditor.clear()
        self.outputArea.clear()
        self.llmBrowser.setHtml(
            "<div style='background-color:#121212; color:#ffffff; padding:15px;'>"
            "LLM response will appear here."
            "</div>"
        )

def set_dark_palette(app):
    """Set a dark color palette for the application."""
    app.setStyle("Fusion")
    dark_palette = QPalette()
    dark_palette.setColor(QPalette.Window, QColor(18, 18, 18))
    dark_palette.setColor(QPalette.WindowText, Qt.white)
    dark_palette.setColor(QPalette.Base, QColor(30, 30, 30))
    dark_palette.setColor(QPalette.AlternateBase, QColor(18, 18, 18))
    dark_palette.setColor(QPalette.ToolTipBase, Qt.white)
    dark_palette.setColor(QPalette.ToolTipText, Qt.white)
    dark_palette.setColor(QPalette.Text, Qt.white)
    dark_palette.setColor(QPalette.Button, QColor(45, 45, 45))
    dark_palette.setColor(QPalette.ButtonText, Qt.white)
    dark_palette.setColor(QPalette.BrightText, Qt.red)
    dark_palette.setColor(QPalette.Link, QColor(42, 130, 218))
    dark_palette.setColor(QPalette.Highlight, QColor(42, 130, 218))
    dark_palette.setColor(QPalette.HighlightedText, Qt.black)
    app.setPalette(dark_palette)
    # Optional: Set a global stylesheet for tooltips.
    app.setStyleSheet("""
        QToolTip {
            color: #ffffff;
            background-color: #2a82da;
            border: 1px solid white;
        }
    """)

if __name__ == "__main__":
    qt_app = QApplication(sys.argv)
    set_dark_palette(qt_app)
    window = MainWindow()
    window.show()
    sys.exit(qt_app.exec_())
