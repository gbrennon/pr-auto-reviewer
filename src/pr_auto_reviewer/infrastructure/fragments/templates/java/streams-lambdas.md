---
id: java-streams-lambdas
language: java
priority: 70
category: best-practices
---

# Java Streams & Lambdas Review

Review the following Java code for proper Stream API and lambda usage:

```java
{{ code }}
```

## Checks

- Streams with side effects inside `map()` or `filter()` (should use `forEach()` or `peek()` only for debugging)
- Using `forEach()` where `collect()` would produce a meaningful result
- Chaining `filter().findFirst()` instead of using a short-circuiting terminal
- `parallel()` stream without justification on small collections
- Lambda that could be a method reference
- `Optional` inside streams where `flatMap(Optional::stream)` (Java 9+) should be used
- Converting stream to list with `.collect(Collectors.toList())` instead of `.toList()` (Java 16+)
- Mixing imperative loops with stream operations on same data

## Good Example

```java
public List<UserDto> findActiveAdmins() {
    return userRepository.findAll().stream()
        .filter(User::isActive)
        .filter(user -> user.getRoles().contains("ADMIN"))
        .map(this::toDto)
        .toList();
}

public Map<String, Long> countByDepartment(List<User> users) {
    return users.stream()
        .filter(u -> u.getDepartment() != null)
        .collect(Collectors.groupingBy(
            User::getDepartment,
            Collectors.counting()
        ));
}
```

## Bad Example

```java
public List<UserDto> findActiveAdmins() {
    List<UserDto> result = new ArrayList<>();
    var users = userRepository.findAll();
    for (User user : users) {  // Imperative loop followed by stream — inconsistent
        if (user.isActive()) {
            result.add(toDto(user));
        }
    }
    users.stream()
        .filter(u -> u.getRoles().contains("ADMIN"))
        .forEach(u -> result.add(toDto(u)));  // Side effect in forEach
    return result;
}
```
