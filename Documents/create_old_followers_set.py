def read_followers(file_path):
    followers = set()
    total_accounts = 0
    with open(file_path, 'r', encoding='utf-8') as file:
        lines = file.readlines()
        i = 0
        while i < len(lines):
            if lines[i].strip():
                username = lines[i].strip()
                followers.add(username)
                total_accounts += 1
                i += 2 if i + 1 < len(lines) and lines[i+1].strip() else 1
            else:
                i += 1
    return followers, total_accounts

def main():
    new_followers, total_accounts = read_followers('Documents\\NewFollowers.txt')
    print(f"Total number of accounts found: {total_accounts}")
    print(f"Total number of unique new followers: {len(new_followers)}")
    print("Set of new followers:")
    for follower in sorted(new_followers):
        print(follower)

if __name__ == "__main__":
    main()
