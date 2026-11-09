"""Demo pharmacy window (fake data only) used to test bot.py."""
import sys
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QPushButton,
    QLabel, QMessageBox, QGroupBox,
)

APP_TITLE = "Pharmacy Prescription System"


class PharmacyApp(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(APP_TITLE)
        self.resize(380, 360)

        self.prescriptions = [
            {"id": "RX-88201", "med": "Compound Pain Gel", "info": "Mix 2% - 50g jar"},
            {"id": "RX-88202", "med": "Amoxicillin 500mg", "info": "Capsules - 30 qty"},
            {"id": "RX-88203", "med": "Compound Hormone Cream", "info": "Topical 1mg/g - 30ml"},
            {"id": "RX-88204", "med": "Ibuprofen 400mg", "info": "Tablets - 20 qty"},
        ]
        self.current_index = -1
        self.has_active_rx = False

        layout = QVBoxLayout()

        self.btn_new = QPushButton("New Prescription")
        self.btn_new.setObjectName("btn_new_rx")
        self.btn_new.clicked.connect(self.load_new_prescription)
        layout.addWidget(self.btn_new)

        box = QGroupBox("Prescription Details")
        box_layout = QVBoxLayout()
        self.lbl_id = QLabel("Rx Number: None")
        self.lbl_id.setObjectName("lbl_rx_id")
        self.lbl_med = QLabel("Medicine: None")
        self.lbl_med.setObjectName("lbl_med_name")
        self.lbl_info = QLabel("Details: None")
        self.lbl_info.setObjectName("lbl_med_info")
        for w in (self.lbl_id, self.lbl_med, self.lbl_info):
            box_layout.addWidget(w)
        box.setLayout(box_layout)
        layout.addWidget(box)

        self.btn_start = self._make_button(layout, "Start Prescription", "btn_start", self.start_process, False)
        self.btn_step = self._make_button(layout, "Complete Preparation Step", "btn_step", self.step_completed, False)
        self.btn_submit = self._make_button(layout, "Submit", "btn_submit", self.submit_rx, False)
        self.btn_back = self._make_button(layout, "Go Back", "btn_back", self.go_back, True)

        self.setLayout(layout)

    @staticmethod
    def _make_button(layout, text, name, handler, enabled):
        b = QPushButton(text)
        b.setObjectName(name)
        b.setEnabled(enabled)
        b.clicked.connect(handler)
        layout.addWidget(b)
        return b

    def load_new_prescription(self):
        # Do not skip a prescription that is still open
        if self.has_active_rx:
            QMessageBox.warning(self, "Notice", "Finish or go back from the current prescription first.")
            return
        if self.current_index + 1 >= len(self.prescriptions):
            QMessageBox.information(self, "Notice", "No more prescriptions in queue.")
            return
        self.current_index += 1
        rx = self.prescriptions[self.current_index]
        self.lbl_id.setText(f"Rx Number: {rx['id']}")
        self.lbl_med.setText(f"Medicine: {rx['med']}")
        self.lbl_info.setText(f"Details: {rx['info']}")
        self.has_active_rx = True
        self.btn_start.setEnabled(True)

    def start_process(self):
        self.btn_step.setEnabled(True)

    def step_completed(self):
        self.btn_submit.setEnabled(True)

    def submit_rx(self):
        QMessageBox.information(self, "Success", "Prescription verified and submitted successfully!")
        self.go_back()

    def go_back(self):
        self.has_active_rx = False
        self.lbl_id.setText("Rx Number: None")
        self.lbl_med.setText("Medicine: None")
        self.lbl_info.setText("Details: None")
        self.btn_start.setEnabled(False)
        self.btn_step.setEnabled(False)
        self.btn_submit.setEnabled(False)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = PharmacyApp()
    window.show()
    sys.exit(app.exec_())
