import sys

class RFIDReader:
    def __init__(self, input_stream=sys.stdin):
        self.input_stream = input_stream

    def get_next_code(self):
        """
        Blocks until a line is read from the input stream, then returns the stripped code.
        """
        code = self.input_stream.readline()
        return code.strip()