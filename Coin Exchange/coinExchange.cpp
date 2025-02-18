#include <iostream>

using namespace std;

// Define return prototype
void billExchange(float amount);
void coinExchange(int amount);

int main() {

    float amount = 0;

    cout << "Enter an amount to exchange into bills and coins: ";
    do{
        cin >> amount;
        if(amount <= 0){
            cout << "Enter an amout greater than 0\n";
        }
    }while(amount <= 0);
    
    billExchange(amount);

    return 0;
}

void billExchange(float amount){
    
    int one = 0, five = 0, ten = 0, twenty = 0, fifty = 0, hundred = 0;

    while(amount >= 1){
        while(amount >= 5){
            while(amount >= 10){
                while(amount >= 20){
                    while(amount >= 50){
                        while(amount >= 100){
                            amount -= 100;
                            hundred++;
                        }
                        if(amount >= 50){
                            amount -= 50;
                            fifty++;
                        }
                    }
                    if(amount >= 20){
                        amount -= 20;
                        twenty++;
                    }
                }
                if(amount >= 10){
                    amount -= 10;
                    ten++;
                }
            }
            if(amount >= 5){
                amount -= 5;
                five++;
            }
        }
        if(amount >= 1){
            amount--;
            one++;
        }
    }

    cout << hundred << " Hundreds, " << fifty << " Fifties, " << twenty << " Twenties, " << ten << " Tens, " << five << " Fives, " << one << " Ones, ";
    
    int newAmount = (int)round(amount *= 100);

    coinExchange(newAmount);
}

void coinExchange(int amount){

    int pennies = 0, nickels = 0, dimes = 0, quarters = 0;
    
    while(amount > 0){
        while(amount > 4){
            while(amount > 9){
                while(amount > 24){
                    amount -= 25;
                    quarters++;
                }
                if(amount > 9){
                    amount -= 10;
                    dimes++;

                }
            }
            if(amount > 4){
                amount -= 5;
                nickels++;
            }
        }
        if(amount > 0){
            amount--;
            pennies++;
        }
    }
    cout << quarters << " Quarters, " << dimes << " Dimes, " << nickels << " Nickels, and " << pennies << " Pennies.\n";
}