import re

def read_followers(file_path):
    with open(file_path, 'r', encoding='utf-8') as file:
        return set(re.sub(r'\s.*', '', line.strip()) for line in file if line.strip())

def write_sorted_followers(file_path, followers):
    with open(file_path, 'w', encoding='utf-8') as file:
        for follower in sorted(followers):
            file.write(f"{follower}\n")

def compare_followers(old_followers, new_followers):
    gained_followers = new_followers - old_followers
    lost_followers = old_followers - new_followers
    return gained_followers, lost_followers

def main():
    old_followers = read_followers('Documents\\UniqueOldFollowers.txt')
    new_followers = read_followers('Documents\\NewFollowers.txt')
    
    write_sorted_followers('Documents\\SortedOldFollowers.txt', old_followers)
    write_sorted_followers('Documents\\SortedNewFollowers.txt', new_followers)
    
    gained, lost = compare_followers(old_followers, new_followers)
    
    print(f"Gained followers ({len(gained)}):")
    for follower in sorted(gained):
        print(follower)
    
    print(f"\nLost followers ({len(lost)}):")
    for follower in sorted(lost):
        print(follower)

    print(f"\nTotal old followers: {len(old_followers)}")
    print(f"Total new followers: {len(new_followers)}")
    print(f"Net change: {len(new_followers) - len(old_followers)}")

if __name__ == "__main__":
    main()
