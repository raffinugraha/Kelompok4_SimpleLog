-- Test 4: Error semantik (deklarasi ganda & variabel tidak dideklarasikan)
boolean a = true;
boolean a = false;
if (a AND z) {
    print(z);
}
