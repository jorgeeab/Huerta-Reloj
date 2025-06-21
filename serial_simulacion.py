import asyncio
import serial_asyncio

class SerialServer(asyncio.Protocol):
    def connection_made(self, transport):
        self.transport = transport
        print('Serial port opened', transport)

    def data_received(self, data):
        print('Data received:', data)
        # Aquí puedes añadir la lógica para manejar los comandos recibidos
        response = b'OK\n'
        self.transport.write(response)

    def connection_lost(self, exc):
        print('Serial port closed')
        self.transport = None

async def main():
    loop = asyncio.get_running_loop()
    port = 'COM3'
    transport, protocol = await serial_asyncio.create_serial_connection(
        loop, SerialServer, port, baudrate=115200
    )

if __name__ == '__main__':
    asyncio.run(main())