#include <iostream>
#include <random>

using namespace std;

// Ignore this
random_device rd;
mt19937 gen(rd());

int bogoSearch(int *arr, int arrSize, int target);

int main(){

    int size, target;

    cout << "Input the size of the array: ";
    cin >> size;

    int arr[size];

    cout << "Input the elements:\n";
    for(int i = 0; i < size; i++){
        cout << "Element #" << i + 1 << ": ";
        cin >> arr[i];
    }

    cout << "Input the target: ";
    cin >> target;

    cout << bogoSearch(arr, size, target);
    
    return 0;
}

// It works trust me
int bogoSearch(int *arr, int arrSize, int target){
    uniform_int_distribution<> distrib(0, arrSize - 1);
    return distrib(gen);
}