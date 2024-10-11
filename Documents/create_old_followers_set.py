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
    new_followers = read_followers('Documents\\NewFollowers.txt')
    print(f"Total number of new followers: {len(new_followers)}")
    print("Set of new followers:")
    for follower in sorted(new_followers):
        print(follower)

if __name__ == "__main__":
    main()
