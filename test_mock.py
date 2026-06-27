from app.detection.stylometric_signal import stylometric_signal

text = """
def add(a, b):
    return a + b
"""

print(stylometric_signal(text))