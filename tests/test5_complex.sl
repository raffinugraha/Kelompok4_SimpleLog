-- Test 5: Ekspresi kompleks & optimasi
boolean p = true;
boolean q = false;
boolean r = p OR q AND NOT p;
if ((p OR q) AND NOT r) {
    print(p);
} else {
    print(r);
}
