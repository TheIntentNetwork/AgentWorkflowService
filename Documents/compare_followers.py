import re

def read_followers(file_path):
    followers = []
    with open(file_path, 'r', encoding='utf-8') as file:
        lines = file.readlines()
        i = 0
        while i < len(lines):
            username = re.sub(r'\s.*', '', lines[i].strip())
            if username:
                followers.append(username)
            i += 2 if i + 1 < len(lines) and lines[i+1].strip() else 1
    return followers

def main():
    new_followers = read_followers('Documents\\NewFollowers.txt')
    old_followers = read_followers('Documents\\OldFollowers.txt')
    
    unique_new_followers = set(new_followers) - set(old_followers)
    
    print(f"New unique followers ({len(unique_new_followers)}):")
    for follower in unique_new_followers:
        print(follower)

    print(f"\nTotal new followers: {len(new_followers)}")
    print(f"Total old followers: {len(old_followers)}")
    print(f"Unique new followers: {len(unique_new_followers)}")

if __name__ == "__main__":
    main()
