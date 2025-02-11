#include <iostream>

using namespace std;

// Define array size
const int SIZE = 10;

// Define sorter prototype
void stalinSort(int (&arr)[SIZE], int &arrSize);

int main() {
    
    // Create the array
    int arr[SIZE];

    // Get the array input
    for(int i = 0; i < SIZE; i++) {
        cout << "Enter index " << i + 1 << ": \n";
        cin >> arr[i];
    }

    // Define a new size that can vary
    int size = SIZE;

    // Call the sorting algorithm
    stalinSort(arr, size);

    // Output the survivors
    for(int j = 0; j < size; j++) {
        cout << arr[j] << " ";
    }

    return 0;
}

void stalinSort(int (&arr)[SIZE], int &arrSize) {

    // Define the last value and the starting array size
    int last = arr[0];
    int newSize = 1;

    // Loop through and kill off the weak numbers
    for(int i = 1; i < arrSize; i++) {
        if(arr[i] >= last) {
            arr[newSize] = arr[i];
            last = arr[i];
            newSize++;
        }
    }

    // Change the array's size
    arrSize = newSize;
}
