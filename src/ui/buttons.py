from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput
from PySide6.QtCore import QUrl

_player = None
_audio = None

def close_window(window):
    window.close()

def go_to_page(window, index):
    window.ui.stackedWidget.setCurrentIndex(index)

def do_silly_sound():
    global _player, _audio
    _player = QMediaPlayer()
    _audio = QAudioOutput()
    _player.setAudioOutput(_audio)
    _player.setSource(QUrl.fromLocalFile("src/ui/silly.mp3"))
    _audio.setVolume(1.0)
    _player.play()