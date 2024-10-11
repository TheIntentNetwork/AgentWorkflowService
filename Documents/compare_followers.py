def read_followers(file_path):
    with open(file_path, 'r') as file:
        return set(line.strip() for line in file if line.strip())

def write_sorted_followers(file_path, followers):
    with open(file_path, 'w') as file:
        for follower in sorted(followers):
            file.write(f"{follower}\n")

def compare_followers(old_followers, new_followers):
    old_set = set(old_followers)
    new_set = set(new_followers)
    
    gained_followers = new_set - old_set
    lost_followers = old_set - new_set
    
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

if __name__ == "__main__":
    main()
