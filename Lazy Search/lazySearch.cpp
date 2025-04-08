#include <iostream>

using namespace std;

const int EFFORT = 3

int lazySearch(int *arr, int arrSize, int target);

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
    cout << lazySearch(arr, size, target);
}

int lazySearch(int *arr, int arrSize, int target){
    int index = -1;
    for(int i = 0; i < EFFORT; i++){
        if(arr[i] == target){
            index = i;
        }
    }
    return index;
}