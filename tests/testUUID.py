# import uuid
# import uuid6
#
# TEST1 = uuid.uuid4()
# test2 = str(TEST1)
# print(TEST1)
# print(type(TEST1))
#
# print(test2)
# print(type(test2))
#
# test3 = uuid.UUID(test2)
#
# print(test3)
# print(type(test3))
# if TEST1 == test3:
#     print(True)
# else:
#     print(False)
#
# if TEST1 == test2:
#     print(True)
# else:
#     print(False)
#
# test4 = uuid6.uuid7()
# print(test4)
#
# Definition for singly-linked list.
def romanToInt( s: str) -> int:
    res = 0
    table = {"I": 1, "V": 5, "X": 10, "L": 50, "C": 100, "D": 500, "M": 1000}

    for i in range(len(s)):
        if s[i] == "I" and s[i+1] in ["V", "X"]:
            res += (table[s[i+1]]-table[s[i]])
            continue
        elif s[i] in ["V", "X"] and s[i+1] == "I":
            continue
        if s[i] == "X" and s[i+1] in ["L", "C"]:
            res += (table[s[i+1]]-table[s[i]])
            continue
        elif s[i] in ["L", "C"] and s[i+1] == "X":
            continue
        if s[i] == "C" and s[i+1] in ["D", "M"]:
            res += (table[s[i+1]]-table[s[i]])
            continue
        elif s[i] in ["D", "M"] and s[i+1] == "C":
            continue
        res += table[s[i]]
    print(res)

romanToInt("IV")
