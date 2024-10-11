import re

def read_followers(file_path):
    with open(file_path, 'r', encoding='utf-8') as file:
        return [re.sub(r'\s.*', '', line.strip()) for line in file if line.strip()]

def main():
    new_followers = read_followers('Documents\\NewFollowers.txt')
    
    print(f"Latest followers ({len(new_followers)}):")
    for follower in new_followers:
        print(follower)

    print(f"\nTotal followers: {len(new_followers)}")

if __name__ == "__main__":
    main()
