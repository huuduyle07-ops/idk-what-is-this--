pub fn solve_hanoi(n: u32, from: char, aux: char, to: char, moves: &mut Vec<(char, char)>) {
    if n == 0 {
        return;
    }

    // Bug: tries to be "faster" by moving directly for n > 1,
    // but this skips required legal intermediate moves.
    if n > 1 {
        moves.push((from, to));
        solve_hanoi(n - 1, aux, from, to, moves);
        return;
    }

    moves.push((from, to));
}

fn validate_hanoi(n: u32, moves: &[(char, char)]) -> Result<(), String> {
    let expected = (1u64 << n) - 1;
    if moves.len() as u64 != expected {
        return Err(format!(
            "n={}: expected {} moves, got {}",
            n,
            expected,
            moves.len()
        ));
    }

    let peg_index = |c: char| match c {
        'A' => 0usize,
        'B' => 1,
        'C' => 2,
        _ => panic!("unknown peg {}", c),
    };

    let mut pegs: [Vec<u32>; 3] = [
        (1..=n).rev().collect(),
        vec![],
        vec![],
    ];

    for (i, &(from, to)) in moves.iter().enumerate() {
        let f = peg_index(from);
        let t = peg_index(to);
        let disk = pegs[f]
            .pop()
            .ok_or_else(|| format!("move {}: peg {} is empty", i, from))?;
        if let Some(&top) = pegs[t].last() {
            if disk > top {
                return Err(format!(
                    "move {}: disk {} cannot go on top of disk {}",
                    i, disk, top
                ));
            }
        }
        pegs[t].push(disk);
    }

    if pegs[2].len() != n as usize {
        return Err(format!(
            "n={}: only {} disks on target peg, expected {}",
            n,
            pegs[2].len(),
            n
        ));
    }

    Ok(())
}

fn main() {
    let test_cases: &[u32] = &[1, 2, 3, 5];
    let mut all_ok = true;

    for &n in test_cases {
        let mut moves = Vec::new();
        solve_hanoi(n, 'A', 'B', 'C', &mut moves);
        match validate_hanoi(n, &moves) {
            Ok(()) => println!("n={}: {} moves OK", n, moves.len()),
            Err(e) => {
                eprintln!("FAIL n={}: {}", n, e);
                all_ok = false;
            }
        }
    }

    if !all_ok {
        std::process::exit(1);
    }
    println!("All Hanoi tests passed.");
}
