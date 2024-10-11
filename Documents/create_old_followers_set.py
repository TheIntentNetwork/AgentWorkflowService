def read_followers(file_path):
    followers = set()
    with open(file_path, 'r', encoding='utf-8') as file:
        lines = file.readlines()
        for i in range(0, len(lines), 2):
            username = lines[i].strip()
            if username:
                followers.add(username)
    return followers

def main():
    old_followers = read_followers('Documents\\OldFollowers.txt')
    print(f"Total number of old followers: {len(old_followers)}")
    print("Set of old followers:")
    for follower in sorted(old_followers):
        print(follower)

if __name__ == "__main__":
    main()
