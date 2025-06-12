#include <iostream>

using namespace std;

int tower(int n, char a, char b, char c) {

    if(n == 1) {
        return 1;
    }

    int sum = 0;

    sum += tower(n - 1, a, c, b);
    sum += 1;
    sum += tower(n - 1, b, a, c);
    
    return sum;
}

int main() {
    cout << tower(3, 'a', 'b', 'c') << endl;
    return 0;
}