#include <iostream>

using namespace std;

int main(){

    int *ptr = new int;

    const int SIZE = 3;
    int *aptr = new int[SIZE];



    delete ptr;
    delete [] aptr;
    aptr = nullptr;

    return 0;
}