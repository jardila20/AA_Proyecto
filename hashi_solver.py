from board import Board

class HashiSolver:
    def __init__(self):
        pass

    def load_board(self, path):
        with open(path, "r") as f:
            lines = [line.strip() for line in f.readlines() if line.strip()]
        return Board.parse_from_lines(lines)

    def print_board(self, board):
        print(board.render())
