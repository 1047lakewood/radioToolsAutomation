# Bug Reproduction Report

## Bug Description
**Issue**: Scheduled hours disappear when selecting a message that has scheduled hours for the first time in the RDS-message configuration window.

## Reproduction Steps
1. ✅ Run the application (`python main_app.py`)
2. ✅ Open the RDS-message configuration window (Click "Configure Messages")
3. ✅ Select a message that has scheduled hours configured
4. ✅ Observe that the scheduled hours disappear from both the time entry field and the underlying data

## Evidence

### Test Configuration
- **Application**: Combined RDS & Intro Loader
- **Test Date**: January 8, 2025
- **Test Script**: `reproduce_bug.py`

### Affected Message
- **Index**: 5
- **Text**: "EZ Pekalach 732 674 9948"
- **Scheduled Days**: Sunday, Monday, Tuesday, Wednesday, Thursday, Friday
- **Original Times**: [{"hour": 13}, {"hour": 14}] (2 hours scheduled)

### Bug Manifestation
- **Before Selection**: Message has 2 scheduled hours (13:00 and 14:00)
- **After Selection**: Message has 0 scheduled hours (empty array)
- **Time Entry Field**: Empty (should display "13, 14")

### Technical Details
- **Location**: `ui_config_window.py` - `on_message_select()` method
- **Symptom**: Time entry field is empty despite having scheduled times in the data
- **Impact**: Users lose their scheduled hour configurations when editing messages

### Reproduction Script Output
```
=== Bug Reproduction Test ===
Step 1: Loading current messages configuration...
Loaded 8 messages
Step 2: Found message with scheduled hours at index 5:
  Text: EZ Pekalach 732 674 9948
  Scheduled Days: ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']
  Scheduled Times: [{'hour': 13}, {'hour': 14}]
  Original times count: 2

Step 3: Creating test application...
Step 4: Opening ConfigWindow...
Step 5: Simulating selection of message at index 5...
  Times in entry field: ''
  Current times in data: []
  Current times count: 0
🐛 BUG REPRODUCED: Times count changed from 2 to 0
   Original: [{'hour': 13}, {'hour': 14}]
   Current:  []
🐛 BUG CONFIRMED: Time entry field is empty!

Step 6: Bug reproduction result: SUCCESS
```

## Files Generated
- `bug_reproduction_state.json` - Contains the before/after state for verification
- `reproduce_bug.py` - Automated reproduction script
- `BUG_REPRODUCTION_REPORT.md` - This report

## Next Steps
- Investigate the `on_message_select()` method in `ui_config_window.py`
- Focus on the time entry field loading logic
- Test the fix with the same reproduction script
- Verify the fix doesn't break other functionality

## Status
- **Bug Confirmed**: ✅ YES
- **Reproduction**: ✅ SUCCESSFUL
- **Ready for Fix**: ✅ YES
