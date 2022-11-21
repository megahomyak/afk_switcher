import wx.adv
import websocket
import json
import uuid
from PIL import Image
from pynput import mouse

OP_HELLO = 0
OP_IDENTIFY = 1
OP_IDENTIFIED = 2
OP_REQUEST = 6
OP_RESPONSE = 7
AFK_SCENE_NAME = "AFK"

socket = websocket.WebSocket()


def recv():
    return json.loads(socket.recv())


def send(data):
    return socket.send(json.dumps(data))


def request(request_type, data):
    d = {"requestType": request_type, "requestId": str(uuid.uuid4())}
    if data:
        d["requestData"] = data
    send({"op": OP_REQUEST, "d": d})


def receive_response():
    while True:
        resp = recv()
        if resp["op"] == OP_RESPONSE:
            try:
                return resp["d"]["responseData"]
            except KeyError:
                pass


def connect():
    global socket
    socket = websocket.WebSocket()
    socket.connect("ws://localhost:4455")
    resp = recv()
    assert resp["op"] == OP_HELLO
    send({"op": OP_IDENTIFY, "d": {"rpcVersion": resp["d"]["rpcVersion"]}})
    assert recv()["op"] == OP_IDENTIFIED


class CannotReconnect(Exception):
    pass


class TaskBarIcon(wx.adv.TaskBarIcon):
    def __init__(self):
        super().__init__()
        self.Bind(wx.adv.EVT_TASKBAR_LEFT_DOWN, lambda _: self.go_afk())
        self.set_icon_color("red")

    def go_active(self, prev_scene_name):
        request(
            "SetCurrentProgramScene",
            {"sceneName": prev_scene_name}
        )
        self.set_icon_color("red")
        return False  # To stop the mouse listener

    def go_afk(self):
        for _ in range(2):
            try:
                request("GetCurrentProgramScene", data=None)
                scenes_info = receive_response()
            except (BrokenPipeError, websocket.WebSocketConnectionClosedException):
                connect()
            else:
                break
        else:
            raise CannotReconnect()
        prev_scene_name = scenes_info["currentProgramSceneName"]
        if prev_scene_name != AFK_SCENE_NAME:
            request(
                "SetCurrentProgramScene",
                {"sceneName": AFK_SCENE_NAME}
            )
            self.set_icon_color("green")
            listener = mouse.Listener(
                on_move=lambda _x, _y: self.go_active(prev_scene_name)
            )
            listener.start()

    def set_icon_color(self, color):
        image = Image.new("RGB", (256, 256), color=color)
        icon = wx.Icon()
        icon.CopyFromBitmap(
            wx.Bitmap.FromBuffer(
               image.width, image.height, image.tobytes()
            )
        )
        self.SetIcon(icon)


class App(wx.App):
    def OnInit(self):
        self.SetTopWindow(wx.Frame(None, -1))
        TaskBarIcon()
        return True


App().MainLoop()
