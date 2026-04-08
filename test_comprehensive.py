import requests

url = 'http://127.0.0.1:7860/api/review'

# User's comprehensive code with 16 bugs
code_sample = '''# 1. Infinite Loop Bug
i = 0
while i < 10:
    print(i)


# 2. Mutable Default Argument Issue
def add_item(item, lst=[]):
    lst.append(item)
    return lst

print(add_item(1))
print(add_item(2))  # Unexpected shared list


# 3. Division by Zero Risk
def divide(a, b):
    return a / b

print(divide(10, 0))


# 4. Modifying List While Iterating
numbers = [1, 2, 3, 4, 5]
for num in numbers:
    if num % 2 == 0:
        numbers.remove(num)

print(numbers)


# 5. Shadowing Built-in
list = [1, 2, 3]
print(list("hello"))


# 6. File Not Closed + No Exception Handling
file = open("data.txt", "r")
content = file.read()
print(content)


# 7. Indentation Error
def greet(name):
print("Hello " + name)


# 8. Logical Error
age = 18
if age > 18:
    print("Adult")
else:
    print("Adult")


# 9. Inefficient Nested Loop
nums = list(range(10000))
for i in nums:
    for j in nums:
        if i == j:
            print(i)


# 10. Missing Return
def square(x):
    result = x * x

print(square(5))


# 11. Race Condition
import threading

counter = 0

def increment():
    global counter
    for _ in range(100000):
        counter += 1

threads = []
for i in range(5):
    t = threading.Thread(target=increment)
    threads.append(t)
    t.start()

for t in threads:
    t.join()

print(counter)


# 12. Wrong Variable Scope
def foo():
    x = 10

foo()
print(x)  # x is not defined


# 13. Type Error
a = "5"
b = 10
print(a + b)


# 14. Off-by-One Error
arr = [1, 2, 3, 4]
for i in range(len(arr)):
    print(arr[i+1])


# 15. Incorrect Exception Catching
try:
    x = int("abc")
except:
    pass  # silently ignores error

print(x)


# 16. Recursive Function Without Base Case
def recurse(n):
    return recurse(n-1)

recurse(5)
'''

try:
    resp = requests.post(
        url,
        json={'code': code_sample, 'language': 'python'},
        timeout=10
    )
    print("=" * 70)
    print("Analysis of Comprehensive Code Sample (16 Bugs)")
    print("=" * 70)
    data = resp.json()
    print(f"\nDetected Bug Type: {data['type'].upper()}")
    print(f"Category: {data.get('category', 'N/A')}")
    print(f"Severity: {data.get('severity', '0')}/5")
    print(f"\nComment: {data['comment']}")
    print(f"\nSuggested Fix:\n{data.get('fix', 'N/A')}")
    print("\n" + "=" * 70)
except Exception as e:
    print(f"Error: {str(e)}")
