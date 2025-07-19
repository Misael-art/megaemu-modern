import os

file_path = 'backend/app/schemas/user.py'

with open(file_path, 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Find and rename UserStatsResponseTemp
temp_start = -1
for i, line in enumerate(lines):
    if 'class UserStatsResponseTemp(BaseSchema):' in line:
        temp_start = i
        lines[i] = line.replace('UserStatsResponseTemp', 'UserStatsResponse')
        break

if temp_start == -1:
    print('Temp class not found')
    exit(1)

# Find the start of the next UserStatsResponse after temp_start
duplicate_start = len(lines)
for j in range(temp_start + 1, len(lines)):
    if 'class UserStatsResponse(BaseSchema):' in lines[j]:
        duplicate_start = j
        break

# Truncate to remove duplicates
lines = lines[:duplicate_start]

# Write back
with open(file_path, 'w', encoding='utf-8') as f:
    f.writelines(lines)
print('Cleanup completed')