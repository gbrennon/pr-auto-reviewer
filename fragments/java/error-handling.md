---
id: java-error-handling
language: java
priority: 85
category: error-handling
---

# Java Error Handling Review

Review the following Java code for proper error handling:

```java
{{ code }}
```

## Checks

- Catching `Exception` or `Throwable` instead of specific exceptions
- Empty catch blocks that silently swallow errors
- Using checked exceptions where runtime exceptions would be more appropriate
- Resources not closed properly (missing try-with-resources)
- Throwing `Exception` from method signatures instead of typed exceptions
- Catching and re-throwing without preserving original cause
- Logging and re-throwing (double logging)
- Using exceptions for control flow

## Good Example

```java
public Optional<User> findUserById(long userId) {
    String sql = "SELECT * FROM users WHERE id = ?";
    try (Connection conn = dataSource.getConnection();
         PreparedStatement stmt = conn.prepareStatement(sql)) {
        stmt.setLong(1, userId);
        try (ResultSet rs = stmt.executeQuery()) {
            if (rs.next()) {
                return Optional.of(mapUser(rs));
            }
            return Optional.empty();
        }
    } catch (SQLException e) {
        throw new DataAccessException("Failed to find user: " + userId, e);
    }
}
```

## Bad Example

```java
public User findUserById(long userId) {
    try {
        Connection conn = dataSource.getConnection();
        PreparedStatement stmt = conn.prepareStatement("SELECT * FROM users");
        ResultSet rs = stmt.executeQuery();
        // Resources never closed — connection leak
        return mapUser(rs);
    } catch (Exception e) {
        e.printStackTrace();  // Silently swallows — caller never knows
        return null;
    }
}
```
