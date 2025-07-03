#!/usr/bin/env python3
"""Mock IMAP server for CI testing without real credentials."""
import asyncio
import email
from datetime import datetime

class MockIMAPServer:
    """Simple mock IMAP server that responds to basic commands."""
    
    def __init__(self, host='localhost', port=10143):
        self.host = host
        self.port = port
        self.messages = [
            {
                'uid': 1,
                'flags': ['\\Seen'],
                'date': datetime.now(),
                'subject': 'Test Email 1',
                'from': 'sender@example.com',
                'to': 'handleylab@gmail.com',
                'body': 'This is a test email for CI'
            }
        ]
    
    async def handle_client(self, reader, writer):
        """Handle IMAP client connections."""
        writer.write(b'* OK IMAP4rev1 Mock server ready\r\n')
        await writer.drain()
        
        while True:
            data = await reader.readline()
            if not data:
                break
                
            command = data.decode().strip()
            tag, cmd, *args = command.split()
            
            if cmd.upper() == 'CAPABILITY':
                writer.write(f'{tag} OK CAPABILITY completed\r\n'.encode())
            elif cmd.upper() == 'LOGIN':
                writer.write(f'{tag} OK LOGIN completed\r\n'.encode())
            elif cmd.upper() == 'SELECT':
                writer.write(f'* 1 EXISTS\r\n'.encode())
                writer.write(f'* 1 RECENT\r\n'.encode())
                writer.write(f'{tag} OK SELECT completed\r\n'.encode())
            elif cmd.upper() == 'LOGOUT':
                writer.write(f'* BYE\r\n'.encode())
                writer.write(f'{tag} OK LOGOUT completed\r\n'.encode())
                break
            else:
                writer.write(f'{tag} NO Unknown command\r\n'.encode())
                
            await writer.drain()
        
        writer.close()
        await writer.wait_closed()
    
    async def start(self):
        """Start the mock IMAP server."""
        server = await asyncio.start_server(
            self.handle_client, self.host, self.port)
        print(f'Mock IMAP server running on {self.host}:{self.port}')
        async with server:
            await server.serve_forever()

if __name__ == '__main__':
    server = MockIMAPServer()
    asyncio.run(server.start())