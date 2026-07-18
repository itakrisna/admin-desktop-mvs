import sys
from PyQt5.QtWidgets import QApplication, QMainWindow, QStackedWidget
from PyQt5.QtGui import QFont

from login import LoginWindow
from database import init_db
from DashboardAdmin import DashboardWindow
from DashboardOwner import OwnerDashboard
from theme import install_text_scale_shortcuts


class MainApp(QMainWindow):
    def __init__(self):
        super().__init__()
        init_db()
        self.setWindowTitle("Melody Violin School Yogyakarta")
        self.resize(1000, 650)
        # Batas lebar/tinggi minimum jendela — mencegah konten (mis. Pengaturan)
        # jadi harus di-scroll ke samping karena jendela ditarik terlalu sempit.
        self.setMinimumSize(1000, 650)

        self.stack = QStackedWidget()
        self.setCentralWidget(self.stack)

        self.login_page = LoginWindow(on_login_success=self.on_login)
        self.admin_dash = DashboardWindow(switch_to_login=self.show_login)
        self.owner_dash = OwnerDashboard(logout_callback=self.show_login)

        for w in (self.login_page, self.admin_dash, self.owner_dash):
            self.stack.addWidget(w)

        self.stack.setCurrentWidget(self.login_page)

        # ── UKURAN TEKS: shortcut Ctrl+'='/'-'/0 didaftarkan sekali di top-level window ini ──
        install_text_scale_shortcuts(self)

    def on_login(self, display_name: str, role: str, username: str = ""):
        if role == "owner":
            self.owner_dash.update_username(display_name)
            self.owner_dash.reset_to_dashboard()
            self.stack.setCurrentWidget(self.owner_dash)
        else:
            self.admin_dash.update_username(display_name)
            self.admin_dash.set_current_user(display_name)
            self.admin_dash.reset_to_dashboard()
            self.stack.setCurrentWidget(self.admin_dash)
        self.showMaximized()

    def show_login(self):
        self.stack.setCurrentWidget(self.login_page)
        self.login_page.reset_fields()
        self.showNormal()
        self.resize(1000, 650)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    # Paksa style Fusion agar QSS custom (hover dropdown, dll) konsisten di semua OS
    app.setStyle("Fusion")
    app.setFont(QFont("Segoe UI", 10))
    window = MainApp()
    window.show()
    sys.exit(app.exec_())
