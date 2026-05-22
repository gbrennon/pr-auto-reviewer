VERDICT: changes_requested

## AI Code Review

**Verdict:** Changes Requested
**Reason:** Sorting by display order is a use case concern, not a storage concern. The repository must return records in storage order and let the caller decide ordering.

### Issues

**1. [HIGH] [architecture] `src/infrastructure/persistence/json_dose_record_repository.rs:91`**

Sorting by display order is a use case concern, not a storage concern. The repository must return records in storage order and let the caller decide ordering.

_Current:_

```
.filter(|r| r.medication_id() == medication_id)
.cloned()
.rev()
.collect()
```

_Suggested:_

```
.filter(|r| r.medication_id() == medication_id)
.cloned()
.collect()
```


**Summary:** Sorting logic should be moved to the application layer.

---
*Review by code-review:latest via local Forgejo*
