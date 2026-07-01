---
id: scala-immutability
language: scala
priority: 80
category: best-practices
---

# Scala Immutability Review

Review the following Scala code for mutability issues:

```scala
{{ code }}
```

## Checks

- Using `var` where `val` would suffice
- Mutable collections (`mutable.ArrayBuffer`, `mutable.Map`) where immutable would work
- `var` with immutable collection vs `val` with mutable collection confusion
- Case classes with `var` fields
- Modifying collection in place with `.update()` or `+=` instead of returning new collection
- Leaking mutable internal state through getters
- Using `null` instead of `Option`

## Good Example

```scala
case class User(
    id: Long,
    name: String,
    roles: List[String] = List.empty
)

def addRole(user: User, role: String): User =
    if user.roles.contains(role) then user
    else user.copy(roles = user.roles :+ role)

def findAdmins(users: List[User]): List[User] =
    users.filter(_.roles.contains("ADMIN"))
```

## Bad Example

```scala
class User(
    var id: Long,        // var — identity can change
    var name: String,    // var — allows mutation
    var roles: List[String] = List.empty  // var + mutable collection confusion likely
)

def addRole(user: User, role: String): Unit = {
    val mutableRoles = collection.mutable.ListBuffer.from(user.roles)
    mutableRoles += role  // Mutating in place instead of returning new User
}
```
