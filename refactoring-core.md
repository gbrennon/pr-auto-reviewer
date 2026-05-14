# BEFORE

```
src/pr_auto_reviewer/core/
├── commands/
│   ├── __init__.py
│   ├── process_issue_commands_command.py
│   └── review_pull_request_command.py
├── dtos/
│   └── __init__.py
├── __init__.py
├── models/
│   ├── entities/
│   │   ├── __init__.py
│   │   ├── issue.py
│   │   └── pull_request.py
│   ├── exceptions/
│   │   ├── domain_error.py
│   │   ├── empty_diff_error.py
│   │   ├── __init__.py
│   │   ├── invalid_comment_id_error.py
│   │   ├── invalid_commit_sha_error.py
│   │   ├── invalid_issue_body_error.py
│   │   ├── invalid_pull_request_id_error.py
│   │   ├── issue_creation_error.py
│   │   ├── llm_unavailable_error.py
│   │   ├── pull_request_not_found_error.py
│   │   └── review_publish_error.py
│   ├── __init__.py
│   └── value_objects/
│       ├── code_review.py
│       ├── comment_id.py
│       ├── commit_sha.py
│       ├── __init__.py
│       ├── issue_command.py
│       ├── item_severity.py
│       ├── pr_comment.py
│       ├── pull_request_diff.py
│       ├── pull_request_id.py
│       ├── review_context.py
│       ├── review_item.py
│       └── review_verdict.py
├── ports/
│   ├── inbound/
│   │   ├── __init__.py
│   │   ├── process_issue_commands_use_case.py
│   │   └── review_pull_request_use_case.py
│   ├── __init__.py
│   └── outbound/
│       ├── changeset_fetcher_port.py
│       ├── command_bus_port.py
│       ├── comment_publisher_port.py
│       ├── comment_reader_port.py
│       ├── __init__.py
│       ├── issue_tracker_port.py
│       ├── llm_review_port.py
│       ├── pull_request_repository.py
│       ├── repository_context_port.py
│       ├── review_publisher_port.py
│       └── review_reader_port.py
└── services/
    ├── __init__.py
    ├── issue_body_builder.py
    ├── issue_command_parser.py
    ├── messages.py
    ├── process_issue_commands_service.py
    ├── review_item_parser.py
    └── review_pull_request_service.py
```

# AFTER
```
src/pr_auto_reviewer/domain/
├── __init__.py
├── entities/
│   ├── __init__.py
│   ├── issue.py
│   ├── pull_request.py
│   └── review_item.py
├── value_objects/
│   ├── __init__.py
│   ├── code_review.py
│   ├── comment_id.py
│   ├── commit_sha.py
│   ├── issue_command.py
│   ├── item_severity.py
│   ├── pr_comment.py
│   ├── pull_request_diff.py
│   ├── pull_request_id.py
│   ├── review_context.py
│   └── review_verdict.py
├── exceptions/
│   ├── __init__.py
│   ├── domain_error.py
│   ├── empty_diff_error.py
│   ├── invalid_comment_id_error.py
│   ├── invalid_commit_sha_error.py
│   ├── invalid_issue_body_error.py
│   ├── invalid_pull_request_id_error.py
│   ├── issue_creation_error.py
│   ├── llm_unavailable_error.py
│   ├── pull_request_not_found_error.py
│   └── review_publish_error.py
└── services/
    ├── __init__.py
    ├── review_item_parser.py
    └── issue_command_parser.py

src/pr_auto_reviewer/application/
├── __init__.py
├── ports/
│   ├── __init__.py
│   ├── inbound/
│   │   ├── __init__.py
│   │   ├── review_pull_request_use_case.py
│   │   └── process_issue_commands_use_case.py
│   └── outbound/
│       ├── __init__.py
│       ├── changeset_fetcher_port.py
│       ├── command_bus_port.py
│       ├── comment_publisher_port.py
│       ├── comment_reader_port.py
│       ├── issue_tracker_port.py
│       ├── llm_review_port.py
│       ├── pull_request_repository.py
│       ├── repository_context_port.py
│       ├── review_publisher_port.py
│       └── review_reader_port.py
├── services/
│   ├── __init__.py
│   ├── review_pull_request_service.py
│   └── process_issue_commands_service.py
├── serializers/
│   ├── __init__.py
│   └── issue_body_builder.py
├── commands/
│   ├── __init__.py
│   ├── review_pull_request_command.py
│   └── process_issue_commands_command.py
├── dtos/
│   └── __init__.py
└── messages/
    ├── __init__.py
    └── messages.py
```

key moves:

- core/ eliminated → Split into domain/ and application/ at package root
- models/ flattened → Direct domain/{entities,value_objects,exceptions}
- review_item.py → domain/entities/ (was misclassified in value_objects/)
- Domain services extracted → review_item_parser.py + issue_command_parser.py → domain/services/ (input boundary guardians)
- Output serializer separated → issue_body_builder.py → application/serializers/ (anti-corruption layer for trackers)
- Messages isolated → messages.py → application/messages/ (use-case coordination artifacts)
- Commands & DTOs → Stay in application/ (orchestration layer)
- Ports structure preserved → application/ports/{inbound,outbound} unchanged
