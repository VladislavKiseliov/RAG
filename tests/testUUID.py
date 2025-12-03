import uuid
import uuid6

TEST1 = uuid.uuid4()
test2 = str(TEST1)
print(TEST1)
print(type(TEST1))

print(test2)
print(type(test2))

test3 = uuid.UUID(test2)

print(test3)
print(type(test3))
if TEST1 == test3:
    print(True)
else:
    print(False)

if TEST1 == test2:
    print(True)
else:
    print(False)

test4 = uuid6.uuid7()
print(test4)

