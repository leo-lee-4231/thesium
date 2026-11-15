import socketserver
import threading

from app.infrastructure.email.sender import EmailConfig, OutboundEmail, send_email


class _FakeSMTP(socketserver.StreamRequestHandler):
    def handle(self) -> None:
        self.wfile.write(b"220 localhost ESMTP\r\n")
        in_data = False
        body: list[bytes] = []
        while True:
            line = self.rfile.readline()
            if not line:
                break
            if in_data:
                if line == b".\r\n":
                    in_data = False
                    self.server.messages.append(b"".join(body))  # type: ignore[attr-defined]
                    self.wfile.write(b"250 OK\r\n")
                else:
                    body.append(line)
                continue
            command = line.decode("ascii", "replace").strip().upper()
            if command.startswith("EHLO"):
                self.wfile.write(b"250-localhost\r\n250 OK\r\n")
            elif (
                command.startswith("HELO")
                or command.startswith("MAIL FROM")
                or command.startswith("RCPT TO")
            ):
                self.wfile.write(b"250 OK\r\n")
            elif command == "DATA":
                in_data = True
                self.wfile.write(b"354 End data with <CR><LF>.<CR><LF>\r\n")
            elif command == "QUIT":
                self.wfile.write(b"221 Bye\r\n")
                break
            else:
                self.wfile.write(b"250 OK\r\n")


async def test_send_email_through_fake_smtp() -> None:
    server = socketserver.ThreadingTCPServer(("127.0.0.1", 0), _FakeSMTP)
    server.daemon_threads = True
    server.messages = []  # type: ignore[attr-defined]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        port = server.server_address[1]
        await send_email(
            EmailConfig(
                host="127.0.0.1",
                port=port,
                from_address="thesium@example.com",
                to_address="owner@example.com",
                use_tls=False,
                use_ssl=False,
            ),
            OutboundEmail(
                to="owner@example.com",
                subject="[Thesium] test",
                text="plain body",
                html="<p>html body</p>",
            ),
        )
    finally:
        server.shutdown()
        server.server_close()
    messages = server.messages  # type: ignore[attr-defined]
    assert len(messages) == 1
    assert b"Subject: [Thesium] test" in messages[0]
    assert b"plain body" in messages[0]
