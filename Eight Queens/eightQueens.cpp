#include <iostream>

using namespace std;

// Board size
const int SIZE = 8;

// Saves the col position of the queen in each row
int board[SIZE];

int solutionCount = 0;

void printBoard() {

    cout << "Solution " << ++solutionCount << ":\n\n ";

    for(int i = 1; i <= SIZE; i++){
        cout << " " << i << " ";
    }

    cout << "\n";

    // Loop through all queens
    for (int i = 0; i < SIZE; ++i) {
        cout << i + 1;
        for (int j = 0; j < SIZE; ++j) {

            if (board[i] == j) {
                cout << " Q ";

            } else {
                cout << " . ";
            
            }
        }
        cout << "\n";
    }
    cout << "\n";
}


bool safe(int row, int col) {

    // Loop through previous placements
    for (int previousRow = 0; previousRow < row; ++previousRow) {
        
        // Check for column conflict: if a queen already exists in the same column
        if (board[previousRow] == col) {
            return false;

        }

        // Check diagonals
        int colDiff = board[previousRow] - col;
        if (colDiff < 0){
            colDiff = -colDiff;
        
        }

        int rowDiff = previousRow - row;
        if (rowDiff < 0){
            rowDiff = -rowDiff;

        }

        if (colDiff == rowDiff) {
            return false;

        }
    }

    return true;

}

void solveQueens(int row) {

    // If all queens have been placed
    if (row == SIZE) {
        
        // Print the solution
        printBoard();
        return;
    }

    // Test each col in the row
    for (int col = 0; col < SIZE; ++col) {

        // Check if spot is safe
        if (safe(row, col)) {

            board[row] = col;

            solveQueens(row + 1);

        }

    }
}

int main() {

    // Start from row 0
    solveQueens(0);
    
    cout << "Total solutions found: " << solutionCount << "\n";

    return 0;
}
