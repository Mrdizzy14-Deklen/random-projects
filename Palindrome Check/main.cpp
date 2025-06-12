#include <iostream>

using namespace std;

bool checkPalindrome(std::string s){

    // An empty string is a palindrome
    if(s == ""){
        return true;
    }

    // Create a temp string to edit
    std::string temp = s;
    temp.pop_back();
    temp.erase(0, 1);

    // Check if first and last character equal, then check the rest
    return (s.front() == s.back()) && checkPalindrome(temp);
}

int main(){

    std::string input;

    cout << "Enter a string\n";

    getline(cin, input);

    if(checkPalindrome(input)){
        cout << input << " is a Palindrome\n";
    }else{
        cout << input << " is not a Palindrome\n";
    }

    return 0;
}