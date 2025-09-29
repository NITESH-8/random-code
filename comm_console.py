from __future__ import annotations

from typing import Optional, List, Callable

from PySide6 import QtCore, QtGui, QtWidgets


class CommConsole(QtWidgets.QWidget):
	"""Generic communication console widget.

	Currently implements a UART terminal with:
	- Port discovery (Windows COMx and others via pyserial when installed)
	- Settings: Baud, Data bits, Parity, Stop bits, Flow control
	- Connect/Disconnect toggle
	- Large read-only log and a compact multi-line input box
	- Enter to send (LF), Shift+Enter for newline, input clears and keeps focus

	Designed to be extended later for SSH / ADB by adding pages to
	`self.proto_stack` while keeping the same log/input area.
	"""

	def __init__(self, parent: Optional[QtWidgets.QWidget] = None) -> None:
		super().__init__(parent)
		self._build_ui()
		self._setup_uart()

	def _build_ui(self) -> None:
		v = QtWidgets.QVBoxLayout(self)
		v.setContentsMargins(0, 0, 0, 0)

		# Protocol selector row (future-proof)
		row = QtWidgets.QHBoxLayout()
		row.setContentsMargins(0, 0, 0, 0)
		row.setSpacing(8)
		row.addWidget(QtWidgets.QLabel("Protocol:"))
		self.proto_combo = QtWidgets.QComboBox()
		self.proto_combo.addItems(["UART", "SSH", "ADB"])  # Extensible
		self.proto_combo.currentIndexChanged.connect(self._on_proto_changed)
		row.addWidget(self.proto_combo)
		row.addStretch(1)
		v.addLayout(row)

		# Protocol-specific control stack
		self.proto_stack = QtWidgets.QStackedWidget()
		v.addWidget(self.proto_stack)

		# UART controls page
		uart_controls = QtWidgets.QWidget()
		u = QtWidgets.QHBoxLayout(uart_controls)
		u.setContentsMargins(0, 0, 0, 0)
		u.setSpacing(8)
		u.addWidget(QtWidgets.QLabel("Port:"))
		self.uart_port_combo = QtWidgets.QComboBox()
		u.addWidget(self.uart_port_combo)
		# Track port changes to swap per-port logs
		self.uart_port_combo.currentTextChanged.connect(self._on_port_changed)
		u.addWidget(QtWidgets.QLabel("Baud:"))
		self.uart_baud = QtWidgets.QComboBox()
		self.uart_baud.addItems(["9600", "19200", "38400", "57600", "115200", "230400", "460800", "921600"]) 
		self.uart_baud.setCurrentText("115200")
		u.addWidget(self.uart_baud)
		u.addWidget(QtWidgets.QLabel("Data:"))
		self.uart_databits = QtWidgets.QComboBox()
		self.uart_databits.addItems(["7", "8"]) 
		self.uart_databits.setCurrentText("8")
		u.addWidget(self.uart_databits)
		u.addWidget(QtWidgets.QLabel("Parity:"))
		self.uart_parity = QtWidgets.QComboBox()
		self.uart_parity.addItems(["None", "Even", "Odd"]) 
		u.addWidget(self.uart_parity)
		u.addWidget(QtWidgets.QLabel("Stop:"))
		self.uart_stop = QtWidgets.QComboBox()
		self.uart_stop.addItems(["1", "1.5", "2"]) 
		u.addWidget(self.uart_stop)
		u.addWidget(QtWidgets.QLabel("Flow:"))
		self.uart_flow = QtWidgets.QComboBox()
		self.uart_flow.addItems(["None", "RTS/CTS", "XON/XOFF"]) 
		u.addWidget(self.uart_flow)
		u.addStretch(1)
		# Clear current port session (placed left of Connect)
		self.uart_clear_btn = QtWidgets.QPushButton("Clear")
		self.uart_clear_btn.setToolTip("Clear only this port's session")
		self.uart_clear_btn.clicked.connect(self._on_uart_clear)
		u.addWidget(self.uart_clear_btn)
		self.uart_connect_btn = QtWidgets.QPushButton("Connect")
		self.uart_connect_btn.setCheckable(True)
		self.uart_connect_btn.toggled.connect(self._on_uart_connect_toggle)
		u.addWidget(self.uart_connect_btn)
		self.proto_stack.addWidget(uart_controls)

		# SSH controls page (placeholder)
		ssh_controls = QtWidgets.QWidget()
		ssh = QtWidgets.QHBoxLayout(ssh_controls)
		ssh.setContentsMargins(0, 0, 0, 0)
		ssh.setSpacing(8)
		ssh.addWidget(QtWidgets.QLabel("SSH Host:"))
		self.ssh_host = QtWidgets.QLineEdit()
		self.ssh_host.setPlaceholderText("hostname or ip")
		ssh.addWidget(self.ssh_host)
		ssh.addWidget(QtWidgets.QLabel("User:"))
		self.ssh_user = QtWidgets.QLineEdit()
		ssh.addWidget(self.ssh_user)
		ssh.addWidget(QtWidgets.QLabel("Port:"))
		self.ssh_port = QtWidgets.QSpinBox()
		self.ssh_port.setRange(1, 65535)
		self.ssh_port.setValue(22)
		ssh.addWidget(self.ssh_port)
		ssh.addStretch(1)
		self.btn_ssh_connect = QtWidgets.QPushButton("Connect (todo)")
		self.btn_ssh_connect.setEnabled(False)
		ssh.addWidget(self.btn_ssh_connect)
		self.proto_stack.addWidget(ssh_controls)

		# ADB controls page (placeholder)
		adb_controls = QtWidgets.QWidget()
		adb = QtWidgets.QHBoxLayout(adb_controls)
		adb.setContentsMargins(0, 0, 0, 0)
		adb.setSpacing(8)
		adb.addWidget(QtWidgets.QLabel("ADB Device:"))
		self.adb_device_combo = QtWidgets.QComboBox()
		self.adb_device_combo.addItem("Select device (todo)")
		adb.addWidget(self.adb_device_combo)
		adb.addStretch(1)
		self.btn_adb_connect = QtWidgets.QPushButton("Connect (todo)")
		self.btn_adb_connect.setEnabled(False)
		adb.addWidget(self.btn_adb_connect)
		self.proto_stack.addWidget(adb_controls)

		# Distinct output log and input box
		self.log = QtWidgets.QPlainTextEdit()
		self.log.setReadOnly(True)
		self.log.setLineWrapMode(QtWidgets.QPlainTextEdit.NoWrap)
		mono = QtGui.QFont("Consolas", 10)
		self.log.setFont(mono)
		self.log.setMinimumHeight(260)
		v.addWidget(self.log, 1)

		self.input = QtWidgets.QPlainTextEdit()
		self.input.setPlaceholderText("Type and press Enter to send. Shift+Enter for newline.")
		self.input.setLineWrapMode(QtWidgets.QPlainTextEdit.NoWrap)
		self.input.setFixedHeight(60)
		self.input.installEventFilter(self)
		v.addWidget(self.input, 0)

	def _setup_uart(self) -> None:
		self._serial = None  # type: ignore[assignment]
		self._poll = QtCore.QTimer(self)
		self._poll.setInterval(100)
		self._poll.timeout.connect(self._poll_uart)
		# Per-port log buffers and current port pointer
		self._port_logs = {}  # type: ignore[var-annotated]
		self._current_port = ""
		self.refresh_ports()
		# Default SOC USB identifier (Windows hwid format substring)
		self._soc_port_id = "VID:PID=067B:23A3"

	def _on_proto_changed(self) -> None:
		idx = self.proto_combo.currentIndex()
		self.proto_stack.setCurrentIndex(idx)
		# Clear the console areas
		if hasattr(self, 'log'):
			self.log.clear()
		if hasattr(self, 'input'):
			self.input.clear()
		# When switching protocols, disconnect UART and clear settings
		if idx != 0:
			self._uart_disconnect_if_needed()
			self._reset_uart_controls(clear_ports=False)
		else:
			# Selected UART: reset and repopulate fresh
			self._reset_uart_controls(clear_ports=True)
			self.refresh_ports()
			self._on_port_changed(self.uart_port_combo.currentText())

	def refresh_ports(self) -> None:
		"""Refresh UART ports list."""
		try:
			from serial.tools import list_ports
			ports = [p.device for p in list_ports.comports()] or ["COM1"]
			self.uart_port_combo.clear()
			self.uart_port_combo.addItems(ports)
		except Exception:
			self.uart_port_combo.clear()
			self.uart_port_combo.addItems(["COM1"]) 

	def _on_uart_connect_toggle(self, checked: bool) -> None:
		if checked:
			port = self.uart_port_combo.currentText()
			try:
				import serial
				baud = int(self.uart_baud.currentText() or 115200)
				bytesize = serial.SEVENBITS if self.uart_databits.currentText() == "7" else serial.EIGHTBITS
				parity_map = {"None": serial.PARITY_NONE, "Even": serial.PARITY_EVEN, "Odd": serial.PARITY_ODD}
				parity = parity_map.get(self.uart_parity.currentText(), serial.PARITY_NONE)
				stop_map = {"1": serial.STOPBITS_ONE, "1.5": serial.STOPBITS_ONE_POINT_FIVE, "2": serial.STOPBITS_TWO}
				stopbits = stop_map.get(self.uart_stop.currentText(), serial.STOPBITS_ONE)
				rx = self.uart_flow.currentText()
				rtscts = (rx == "RTS/CTS")
				xonxoff = (rx == "XON/XOFF")
				self._serial = serial.Serial(port=port, baudrate=baud, bytesize=bytesize, parity=parity, stopbits=stopbits, rtscts=rtscts, xonxoff=xonxoff, timeout=0)
				self.uart_connect_btn.setText("Disconnect")
				self._poll.start()
				# Initialize per-port log buffer and set current
				self._current_port = port
				# Ensure terminal shows buffer for this port
				self._port_logs.setdefault(port, "")
				self._current_port = port
				if hasattr(self, 'log'):
					self.log.setPlainText(self._port_logs.get(port, ""))
					self.log.moveCursor(QtGui.QTextCursor.End)
			except ImportError:
				QtWidgets.QMessageBox.critical(
					self,
					"Serial Module Missing",
					"pyserial is not installed. Install it with:\n\n  python -m pip install pyserial\n\nThen restart the app."
				)
				self.uart_connect_btn.setChecked(False)
			except Exception as e:
				msg = str(e)
				if isinstance(e, PermissionError) or "access is denied" in msg.lower() or "busy" in msg.lower() or "resource busy" in msg.lower():
					msg = f"Port {port} is busy or access is denied. Close other apps and try again.\n\nDetails: {str(e)}"
				elif isinstance(e, FileNotFoundError) or "no such file" in msg.lower() or "cannot find the file" in msg.lower():
					msg = f"Port {port} was not found. Check the device and try again.\n\nDetails: {str(e)}"
				QtWidgets.QMessageBox.critical(self, "Open Port Failed", msg)
				self.uart_connect_btn.setChecked(False)
		else:
			self._poll.stop()
			try:
				if self._serial is not None:
					self._serial.close()
					self._serial = None
			except Exception:
				pass
			self.uart_connect_btn.setText("Connect")

	def _on_uart_clear(self) -> None:
		"""Clear only the currently selected port's session log."""
		try:
			port = self.uart_port_combo.currentText()
			self._port_logs[port] = ""
			if hasattr(self, 'log'):
				self.log.clear()
		except Exception:
			pass

	# ===== Programmatic helpers for external workflows =====
	def find_linux_port(self, soc_port_id: Optional[str] = None) -> Optional[str]:
		"""Return the COM port name whose hwid contains the given VID:PID.

		Chooses the lowest COM number if multiple match.
		"""
		try:
			from serial.tools import list_ports
			needle = (soc_port_id or self._soc_port_id).strip()
			candidates: List[str] = []
			for p in list_ports.comports():
				try:
					hwid = getattr(p, 'hwid', '') or ''
					if needle and needle in hwid:
						candidates.append(p.device)
				except Exception:
					pass
			if not candidates:
				return None
			def _com_num(name: str) -> int:
				import re
				m = re.search(r"COM(\d+)$", name.upper())
				return int(m.group(1)) if m else 1_000_000
			candidates.sort(key=_com_num)
			return candidates[0]
		except Exception:
			return None

	def connect_to_port(self, port: str, baud: int = 115200) -> bool:
		"""Connect to a specific port with given baud. Returns True on success."""
		try:
			# Ensure the combo contains the port and selects it
			idx = self.uart_port_combo.findText(port)
			if idx < 0:
				self.uart_port_combo.addItem(port)
				idx = self.uart_port_combo.findText(port)
			self.uart_port_combo.setCurrentIndex(max(0, idx))
			self.uart_baud.setCurrentText(str(int(baud)))
			# Toggle connect; handler will open serial and start polling
			self.uart_connect_btn.setChecked(True)
			# Success if we are connected and serial is open
			return bool(self._serial)
		except Exception as e:
			QtWidgets.QMessageBox.critical(self, "Open Port Failed", str(e))
			return False

	def send_commands(self, commands: List[str], spacing_ms: int = 300, on_complete: Optional[Callable[[], None]] = None) -> None:
		"""Send a list of shell commands over UART, separated by newlines.

		Adds a trailing newline to each item and spaces them in time to avoid
		bursting. Calls on_complete after the last command.
		"""
		if not commands:
			if on_complete:
				on_complete()
			return
		queue = list(commands)
		timer = QtCore.QTimer(self)
		timer.setInterval(max(50, int(spacing_ms)))
		def _flush_next():
			if not queue:
				timer.stop()
				if on_complete:
					on_complete()
				return
			cmd = queue.pop(0)
			try:
				if self._serial is not None:
					self._serial.write((cmd + "\n").encode())
					# Echo into buffer/UI to keep log coherent
					port = self.uart_port_combo.currentText()
					self._port_logs[port] = self._port_logs.get(port, "") + cmd + "\n"
					if hasattr(self, 'log'):
						self.log.moveCursor(QtGui.QTextCursor.End)
						self.log.insertPlainText(cmd + "\n")
						self.log.moveCursor(QtGui.QTextCursor.End)
			except Exception:
				pass
		timer.timeout.connect(_flush_next)
		timer.start()
		# Send first immediately
		_flush_next()

	def disconnect_serial(self) -> None:
		"""Disconnect if currently connected."""
		self._uart_disconnect_if_needed()

	def _uart_disconnect_if_needed(self) -> None:
		if self.uart_connect_btn.isChecked():
			self.uart_connect_btn.setChecked(False)

	def _on_port_changed(self, port: str) -> None:
		"""Switch visible log to the selected port and clear the UI for new sessions.

		- Stores the current text into the current port's buffer
		- Loads the buffer for the newly selected port
		- If not connected, still swaps buffers so logs persist per-port
		"""
		try:
			# Save current log text into previous port buffer
			prev = getattr(self, '_current_port', '')
			if prev and hasattr(self, 'log'):
				self._port_logs[prev] = self.log.toPlainText()
			# Load new port buffer
			self._current_port = port
			if hasattr(self, 'log'):
				self.log.setPlainText(self._port_logs.get(port, ""))
				self.log.moveCursor(QtGui.QTextCursor.End)
		except Exception:
			pass

	def _reset_uart_controls(self, clear_ports: bool) -> None:
		"""Reset UART controls to defaults. Optionally clear the port list."""
		if clear_ports:
			self.uart_port_combo.clear()
		self.uart_baud.setCurrentText("115200")
		self.uart_databits.setCurrentText("8")
		self.uart_parity.setCurrentText("None")
		self.uart_stop.setCurrentText("1")
		self.uart_flow.setCurrentText("None")

	def _poll_uart(self) -> None:
		try:
			if self._serial is not None and self._serial.in_waiting:
				data = self._serial.read(self._serial.in_waiting)
				if data:
					try:
						text = data.decode(errors="replace")
					except Exception:
						text = str(data)
					# Append to per-port log buffer and UI
					port = self.uart_port_combo.currentText()
					self._port_logs[port] = self._port_logs.get(port, "") + text
					if hasattr(self, 'log'):
						self.log.moveCursor(QtGui.QTextCursor.End)
						self.log.insertPlainText(text)
						self.log.moveCursor(QtGui.QTextCursor.End)
		except Exception as e:
			self._poll.stop()
			try:
				if self._serial is not None:
					self._serial.close()
					self._serial = None
			except Exception:
				pass
			QtWidgets.QMessageBox.warning(self, "Serial Disconnected", f"Serial port error: {str(e)}\nThe connection has been closed.")
			self.uart_connect_btn.setChecked(False)

	def _on_send(self) -> None:
		msg = (self.input.toPlainText().rstrip("\r\n").split("\n")[-1] if hasattr(self, 'input') else "")
		if not msg:
			return
		try:
			if self._serial is not None:
				self._serial.write((msg + "\n").encode())
				# Echo into per-port log and keep caret at end
				port = self.uart_port_combo.currentText()
				self._port_logs[port] = self._port_logs.get(port, "") + msg + "\n"
				if hasattr(self, 'log'):
					self.log.moveCursor(QtGui.QTextCursor.End)
					self.log.insertPlainText("\n")
					self.log.moveCursor(QtGui.QTextCursor.End)
				if hasattr(self, 'input'):
					self.input.clear()
		except Exception as e:
			QtWidgets.QMessageBox.critical(self, "Serial Error", str(e))

	def eventFilter(self, source, event):  # type: ignore[override]
		try:
			if hasattr(self, 'input') and source is self.input and isinstance(event, QtGui.QKeyEvent):
				if event.type() == QtCore.QEvent.KeyPress and event.key() in (QtCore.Qt.Key_Return, QtCore.Qt.Key_Enter):
					if event.modifiers() & QtCore.Qt.ShiftModifier:
						self.input.insertPlainText("\n")
					else:
						self._on_send()
						return True
		except KeyboardInterrupt:
			# Ignore Ctrl+C interrupts when running from a console to avoid PySide error dialog
			return False
		except Exception:
			pass
		return super().eventFilter(source, event)


