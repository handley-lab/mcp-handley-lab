#!/usr/bin/env python3
"""Mock IMAP server for CI testing without real credentials."""
import socket
import threading
from datetime import datetime


class MockIMAPServer:
    """Simple mock IMAP server that responds to basic commands."""

    def __init__(self, host="localhost", port=10143):
        self.host = host
        self.port = port
        self.running = False
        self.server_socket = None
        self.messages = [
            {
                "uid": 1,
                "flags": ["\\Seen"],
                "date": datetime.now(),
                "subject": "Test Email 1",
                "from": "sender@example.com",
                "to": "handleylab@gmail.com",
                "body": "This is a test email for CI",
            }
        ]

    def add_test_message(self, test_id, subject, body="Test email body"):
        """Add a test message with specific test ID for verification."""
        self.messages.append(
            {
                "uid": len(self.messages) + 1,
                "flags": ["\\Recent"],
                "date": datetime.now(),
                "subject": subject,
                "from": "test@example.com",
                "to": "handleylab@gmail.com",
                "body": f"{body}\n\nTest ID: {test_id}",
            }
        )

    def handle_client(self, client_socket):
        """Handle IMAP client connections."""
        try:
            client_socket.send(b"* OK IMAP4rev1 Mock server ready\r\n")

            while True:
                data = client_socket.recv(1024)
                if not data:
                    break

                command = data.decode().strip()
                if not command:
                    continue

                parts = command.split()
                if len(parts) < 2:
                    continue

                tag, cmd = parts[0], parts[1]

                if cmd.upper() == "CAPABILITY":
                    client_socket.send(f"{tag} OK CAPABILITY completed\r\n".encode())
                elif cmd.upper() == "LOGIN":
                    client_socket.send(f"{tag} OK LOGIN completed\r\n".encode())
                elif cmd.upper() == "SELECT":
                    client_socket.send(f"* {len(self.messages)} EXISTS\r\n".encode())
                    client_socket.send(f"* {len(self.messages)} RECENT\r\n".encode())
                    client_socket.send(f"{tag} OK SELECT completed\r\n".encode())
                elif cmd.upper() == "FETCH":
                    # Handle FETCH commands to serve test messages
                    if len(parts) >= 3:
                        msg_num = parts[2]
                        fetch_items = " ".join(parts[3:])
                        if (
                            "BODY" in fetch_items.upper()
                            or "RFC822" in fetch_items.upper()
                        ) and self.messages:
                            msg = self.messages[0]
                            email_content = f"""Subject: {msg['subject']}
From: {msg['from']}
To: {msg['to']}
Date: {msg['date'].strftime('%a, %d %b %Y %H:%M:%S +0000')}

{msg['body']}"""
                            client_socket.send(
                                f"* {msg_num} FETCH (RFC822 {{{len(email_content)}}}\r\n".encode()
                            )
                            client_socket.send(email_content.encode())
                            client_socket.send(b")\r\n")
                    client_socket.send(f"{tag} OK FETCH completed\r\n".encode())
                elif cmd.upper() == "LOGOUT":
                    client_socket.send(b"* BYE\r\n")
                    client_socket.send(f"{tag} OK LOGOUT completed\r\n".encode())
                    break
                else:
                    client_socket.send(f"{tag} NO Unknown command\r\n".encode())

        except (ConnectionResetError, BrokenPipeError):
            pass
        finally:
            client_socket.close()

    def start(self):
        """Start the mock IMAP server."""
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_socket.bind((self.host, self.port))
        self.server_socket.listen(5)
        self.running = True

        print(f"Mock IMAP server running on {self.host}:{self.port}")

        while self.running:
            try:
                client_socket, addr = self.server_socket.accept()
                client_thread = threading.Thread(
                    target=self.handle_client, args=(client_socket,)
                )
                client_thread.daemon = True
                client_thread.start()
            except OSError:
                break

    def stop(self):
        """Stop the mock IMAP server."""
        self.running = False
        if self.server_socket:
            self.server_socket.close()


if __name__ == "__main__":
    server = MockIMAPServer()
    try:
        server.start()
    except KeyboardInterrupt:
        server.stop()
