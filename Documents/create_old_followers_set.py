def read_followers(file_path):
    followers = []
    with open(file_path, 'r', encoding='utf-8') as file:
        lines = file.readlines()
        i = 0
        while i < len(lines):
            if lines[i].strip():
                username = lines[i].strip()
                followers.append(username)
                i += 2 if i + 1 < len(lines) and lines[i+1].strip() else 1
            else:
                i += 1
    return followers

def main():
    new_followers = read_followers('Documents\\NewFollowers.txt')
    old_followers = read_followers('Documents\\OldFollowers.txt')

    unique_new_followers = set(new_followers) - set(old_followers)
    
    print(f"Total number of new accounts found: {len(new_followers)}")
    print(f"Total number of old accounts found: {len(old_followers)}")
    print(f"Total number of unique new followers: {len(unique_new_followers)}")
    
    print("\nList of newest accounts:")
    for follower in sorted(unique_new_followers):
        print(follower)

if __name__ == "__main__":
    main()
