# Why Frontend Shows Mock Data - And How to Verify Real API Works

## ✅ THE REAL API IS WORKING

Proof from direct testing:
```
Code with bugs:
try:
    x = int("abc")
except:
    pass

def recurse(n):
    return recurse(n-1)

API Response: 2 bugs detected
1. Infinite recursion - Confidence: 0.87 (REAL)
2. Bare except - Confidence: 0.96 (REAL)
```

**But the Browser Shows: "Approved - Style - 50% Confidence"** ← This is the mock fallback!

---

## 🔍 Why Frontend Shows Mock Data

The frontend falls back to mock when:
1. ✗ API throws an error
2. ✗ API response isn't being received
3. ✗ Network issue / CORS problem
4. ✗ Frontend catches any exception

When this happens, instead of showing real API bugs, it shows a generic "No obvious bugs - style - logging suggestion"

---

## 🛠️ How to Verify Real vs Mock Data

### **Step 1: Open Browser DevTools**
- Press `F12` in your browser
- Go to **Console** tab
- Clear any old messages

### **Step 2: Paste This Code in the CodeBug Frontend:**
```python
try:
    x = int("abc")
except:
    pass

def recurse(n):
    return recurse(n-1)
```

**DO NOT** include `recurse(5)` at the end - that causes infinite recursion

### **Step 3: Click Analyze**

### **Step 4: Check Console Output**

**If you see REAL API data:**
```
✓ Real API response received: {
  bugs_found: 2,
  bugs: [
    { comment: "Infinite recursion...", confidence: 0.87 },
    { comment: "Bare except...", confidence: 0.96 }
  ]
}
```

**OR if you see MOCK fallback:**
```
⚠ API call failed: [error message]
Using fallback local analysis...
Fallback result: { type: 'approve', ... }
```

---

## ✅ Debug Checklist

1. **Check if API is responding:**
   - Open console (F12)
   - Look for "✓ Real API response received"
   - If you see "⚠ API call failed", note the error

2. **Common errors and fixes:**
   - `ERR_CONNECTION_REFUSED` → API server not running
   - `ERR_NETWORK_TIMEOUT` → API is hanging (code with infinite recursion)
   - `CORS error` → Cross-origin issue
   - `404 Not Found` → Wrong endpoint path

3. **Test with Safe Code:**
   - Start with simple code: `x = 5`
   - Gradually add complexity
   - AVOID code with infinite recursion at module level

---

## 📊 Real vs Mock Data Indicators

###Real Data (from API):
- ✓ Confidence: 0.75-0.99 (never 0.5 or 1.0)
- ✓ Multiple bugs shown
- ✓ Specific error types (SQL injection, bare except, etc.)
- ✓ Severity: 2-5
- ✓ Specific line hints: "Line 3", "Line 5"

### Mock Data (fallback):
- ✗ Confidence: 1.0 (clean code) or varies
- ✗ Generic suggestions: "logging module"
- ✗ Category: mostly "style"
- ✗ Line hint: "Not specified"

---

## 🚨 Current Known Issue

**The frontend is currently showing mock data for all requests** because there might be:
1. A network/CORS issue
2. The API endpoint returning an error
3. Browser security restrictions

**Solution:** 
1. Check browser console (F12)
2. Look for the error message
3. Report what you see

---

##✅ What to Try

### Option 1: Direct Test
```javascript
// Paste in browser console:
fetch('/api/review', {
  method: 'POST',
  headers: {'Content-Type': 'application/json'},
  body: JSON.stringify({
    code: 'try:\n    x = int("abc")\nexcept:\n    pass',
    language: 'python'
  })
})
.then(r => r.json())
.then(data => console.log(data))
```

### Option 2: Test with cURL
```powershell
$body = @{
  code = 'try:\n    x = int("abc")\nexcept:\n    pass'
  language = 'python'
} | ConvertTo-Json

Invoke-WebRequest -Uri http://127.0.0.1:7860/api/review `
  -Method POST `
  -ContentType 'application/json' `
  -Body $body
```

---

## ✅ NEXT STEPS

1. **Verify API is running:**
   ```bash
   .venv\Scripts\python -m uvicorn main:app --host 127.0.0.1 --port 7860
   ```

2. **Open browser console (F12)**

3. **Paste code and analyze - check console output**

4. **Share console error message if fallback appears**

---

The REAL API **IS WORKING**. We just need to figure out why the frontend isn't showing it. 🔍
