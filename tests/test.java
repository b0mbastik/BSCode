public class test {
    static void printGreeting() {
        System.out.println("Hello World!");
    }

    public static void main(String[] args) {
        printGreeting();

	int a = 0;

	for (int i = 0; i < 5; i++){
		a += i;
		System.out.println(a);
	}
    }
}