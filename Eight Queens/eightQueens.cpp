#include <iostream>

// Chessboard Size
const int SIZE = 8;

// Chessboard contents
int board[SIZE][SIZE];

// Number of solutions found
int sCount = 0;


void printBoard() {
    std::cout << "Solution " << ++sCount << ":\n";
    for (int i = 0; i < SIZE; ++i) {
        for (int j = 0; j < SIZE; ++j) {
            if (board[i][] == j) {
                std::cout << " Q "; // Queen is at this position
            } else {
                std::cout << " * "; // Empty square
            }
        }
        std::cout << "\n";
    }
    std::cout << "\n";
}

/**
 * @brief Checks if placing a queen at (row, col) is safe from previously placed queens.
 *
 * @param row The current row to place a queen.
 * @param col The current column to place a queen.
 * @return true if it's safe to place a queen, false otherwise.
 */
bool isSafe(int row, int col) {
    // Iterate through all previously placed queens (in rows 0 to row-1)
    for (int previousRow = 0; previousRow < row; ++previousRow) {
        // Check for column conflict: if a queen already exists in the same column
        if (board[previousRow] == col) {
            return false;
        }

        // Check for diagonal conflict:
        // Replaced std::abs with a manual absolute difference calculation
        int colDiff = board[previousRow] - col;
        if (colDiff < 0) colDiff = -colDiff; // Manual abs for column difference

        int rowDiff = previousRow - row;
        if (rowDiff < 0) rowDiff = -rowDiff; // Manual abs for row difference

        // If these differences are equal, they are on the same diagonal.
        if (colDiff == rowDiff) {
            return false;
        }
    }
    // If no conflicts found, it's safe to place the queen
    return true;
}

/**
 * @brief Recursive function to solve the N-Queens problem.
 * Attempts to place a queen in the current 'row'.
 *
 * @param row The current row to place a queen.
 */
void solveQueens(int row) {
    // Base Case: If all queens have been placed (current row is beyond the board)
    if (row == N) {
        printBoard(); // A solution has been found, print it
        return;
    }

    // Recursive Step: Try placing a queen in each column of the current row
    for (int col = 0; col < N; ++col) {
        // Check if placing a queen at (row, col) is safe
        if (isSafe(row, col)) {
            // Place the queen: Store the column in the current row
            board[row] = col;

            // Recursively call solveQueens for the next row
            solveQueens(row + 1);

            // Backtrack: No explicit "unplacing" is needed here because
            // the next iteration of the loop (or the return to the previous
            // recursive call) will overwrite board[row] if a different path is taken.
            // This implicitly "removes" the queen from the current (row, col)
            // when exploring other possibilities.
        }
    }
}

/**
 * @brief Main function to start the Eight Queens solver.
 * @return 0 on successful execution.
 */
int main() {
    std::cout << "Solving the " << N << " Queens Problem...\n\n";

    // Start the recursive process from the first row (row 0)
    solveQueens(0);

    // Report total solutions found
    if (solutionCount == 0) {
        std::cout << "No solutions found for " << N << " queens.\n";
    } else {
        std::cout << "Total solutions found: " << solutionCount << "\n";
    }

    return 0;
}
