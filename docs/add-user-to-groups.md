# add-user-to-groups

Add a user to one or more XNAT project groups with role-based access.

## Overview

The `add-user-to-groups` command allows XNAT administrators to grant users access to projects by adding them to project groups. This is useful for:

- Onboarding new team members to multiple projects at once
- Granting access with specific roles (owner, member, collaborator)
- Batch user management across projects

## XNAT Group Naming Convention

XNAT project groups follow a naming convention:

```
{PROJECT_ID}_{SITE}_{ROLE}
```

| Component | Description | Examples |
|-----------|-------------|----------|
| `PROJECT_ID` | The XNAT project identifier | `ABC01`, `STUDY01`, `DEMO` |
| `SITE` | Site/institution code | `SITE1`, `MAIN`, `LAB` |
| `ROLE` | Access level | `owner`, `member`, `collaborator` |

**Example group names:**
- `ABC01_SITE1_owner` - Owner access to ABC01 at SITE1
- `STUDY01_MAIN_member` - Member access to STUDY01 at MAIN site
- `DEMO_LAB_collaborator` - Collaborator access to DEMO at LAB site

## XNAT Roles Explained

| Role | Permissions |
|------|-------------|
| **owner** | Full access: create/delete subjects, manage users, modify project settings |
| **member** | Standard access: create/edit subjects and experiments, upload data |
| **collaborator** | Read-only access: view data but cannot modify |

## Usage

```bash
xio add-user-to-groups USERNAME [GROUPS...] [OPTIONS]
```

### Arguments

| Argument | Description |
|----------|-------------|
| `USERNAME` | XNAT username to add to groups |
| `GROUPS` | Optional: specific group names to add user to |

### Options

| Option | Description |
|--------|-------------|
| `--projects PROJECT1,PROJECT2,...` | Comma-separated list of project IDs |
| `--role {owner,member,collaborator}` | Role to assign (default: `member`) |
| `--site SITE` | Site suffix for group names (e.g., `SITE1`) |
| `--env {dev,test,prod}` | Environment name or path to .env file |
| `-v, --verbose` | Enable verbose logging |

## Examples

### Using Convenience Flags (Recommended)

Add a user to multiple projects with the same role:

```bash
# Add user as member to three projects
xio add-user-to-groups jsmith \
  --projects "ABC01,STUDY01,DEMO" \
  --role member \
  --site SITE1 \
  --env prod -v

# This creates groups: ABC01_SITE1_member, STUDY01_SITE1_member, DEMO_SITE1_member
```

Add a user as owner:

```bash
xio add-user-to-groups jsmith \
  --projects "ABC01" \
  --role owner \
  --site SITE1 \
  --env prod -v
```

### Using Direct Group Names

For more control, specify exact group names:

```bash
# Add user to specific groups
xio add-user-to-groups jsmith \
  ABC01_SITE1_owner STUDY01_SITE1_member DEMO_LAB_collaborator \
  --env prod -v
```

### Mixing Both Approaches

You can combine `--projects` with direct group names:

```bash
# Add as member to ABC01,STUDY01 AND owner to DEMO
xio add-user-to-groups jsmith \
  DEMO_SITE1_owner \
  --projects "ABC01,STUDY01" \
  --role member \
  --site SITE1 \
  --env prod -v
```

### Common Workflows

#### Onboard New Team Member

```bash
# Grant member access to all team projects
xio add-user-to-groups newuser123 \
  --projects "ABC01,DEF01,GHI01,JKL01" \
  --role member \
  --site SITE1 \
  --env prod -v
```

#### Grant Principal Investigator Access

```bash
# Grant owner access to their project
xio add-user-to-groups pi_username \
  --projects "ABC01" \
  --role owner \
  --site SITE1 \
  --env prod -v
```

#### Add External Collaborator (Read-Only)

```bash
# Grant read-only access
xio add-user-to-groups external_user \
  --projects "ABC01,DEF01" \
  --role collaborator \
  --site SITE1 \
  --env prod -v
```

## Output

The command reports success and failures:

```
User jsmith added to groups:
  - ABC01_SITE1_member
  - STUDY01_SITE1_member
  - DEMO_SITE1_member
```

If some groups fail:

```
User jsmith added to groups:
  - ABC01_SITE1_member
Failed to add user to groups:
  - INVALID_GROUP: failed
```

### Exit Codes

| Code | Meaning |
|------|---------|
| `0` | All groups added successfully |
| `1` | Some groups failed to add |

## Programmatic Usage

```python
from xnatio import XNATClient, load_config

config = load_config()
client = XNATClient.from_config(config)

# Add user to groups
result = client.add_user_to_groups(
    username="jsmith",
    groups=["ABC01_SITE1_member", "STUDY01_SITE1_member", "DEMO_SITE1_owner"],
)

# Check results
if result["added"]:
    print(f"Successfully added to: {result['added']}")
if result["failed"]:
    print(f"Failed to add to: {result['failed']}")
```

### Method Signature

```python
def add_user_to_groups(
    self,
    username: str,
    groups: list[str],
) -> dict[str, object]:
    """
    Add a user to one or more XNAT groups.

    Parameters
    ----------
    username : str
        XNAT username to add to groups
    groups : list[str]
        List of group names (e.g., ['ABC01_SITE1_member', 'STUDY01_SITE1_owner'])

    Returns
    -------
    dict with keys:
        - added: list of groups user was successfully added to
        - failed: dict of {group: error_message}
    """
```

## Troubleshooting

### User Not Found

**Cause:** The username doesn't exist in XNAT.

**Solution:** Verify the username in XNAT Admin > Users.

### Group Not Found

**Cause:** The group name is incorrect or the project doesn't exist.

**Solution:**
- Verify project ID is correct
- Check site code matches your XNAT configuration
- Ensure the project has the expected groups created

### Permission Denied

**Cause:** Your XNAT user doesn't have admin privileges.

**Solution:** This command requires XNAT admin access or project owner privileges.

### Partial Success (Exit Code 1)

**Cause:** Some groups were added but others failed.

**Solution:** Check the error output for specific failures and resolve individually.

## Best Practices

1. **Use `--role member` by default** - Grant minimum necessary permissions
2. **Use convenience flags** - Less error-prone than typing exact group names
3. **Verify before production** - Test with `--env test` first
4. **Document access grants** - Keep records of who has access to which projects
5. **Review periodically** - Remove access for users who no longer need it

## See Also

- [XNAT User Administration](https://wiki.xnat.org/documentation/xnat-administration/user-management)
- [resource-upload-vs-dicom-upload.md](./resource-upload-vs-dicom-upload.md) - Upload methods
- [refresh-catalogs.md](./refresh-catalogs.md) - Catalog refresh
- [rename-subjects-pattern.md](./rename-subjects-pattern.md) - Subject renaming
