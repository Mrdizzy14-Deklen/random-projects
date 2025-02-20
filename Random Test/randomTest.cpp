#include <iostream>
#include <memory>
#include <cctype>

using namespace std;

void *getNumbers(int);

int main(){

    int *ptr = new int;

    const int SIZE = 3;
    int *aptr = new int[SIZE];
    aptr[0] = 5;

    cout << aptr[0];
    delete ptr;
    delete [] aptr;
    aptr = nullptr;

    return 0;
}

void *getNumbers(int val){
    int *ptr = new int[val];
    return 0;
}