import UIKit

final class WitnessField: UITextField, UIGestureRecognizerDelegate {
    var masksAccessibility = false
    var refusesSelectionDeletion = false
    var selectionDeletionPending = false
    var taps = 0
    var selections = 0
    var rejected = 0
    var changed: (() -> Void)?

    override init(frame: CGRect) {
        super.init(frame: frame)
        let tap = UITapGestureRecognizer(target: self, action: #selector(recordTap))
        tap.cancelsTouchesInView = false
        tap.delegate = self
        addGestureRecognizer(tap)
    }

    required init?(coder: NSCoder) { fatalError() }

    @objc private func recordTap() {
        taps += 1
        changed?()
    }

    func gestureRecognizer(_ gestureRecognizer: UIGestureRecognizer, shouldRecognizeSimultaneouslyWith otherGestureRecognizer: UIGestureRecognizer) -> Bool { true }

    override func selectAll(_ sender: Any?) {
        selections += 1
        selectionDeletionPending = refusesSelectionDeletion
        super.selectAll(sender)
        changed?()
    }

    override var accessibilityValue: String? {
        get {
            if masksAccessibility, let text, !text.isEmpty {
                return String(repeating: "\u{2022}", count: max(1, text.count / 2))
            }
            return super.accessibilityValue
        }
        set { super.accessibilityValue = newValue }
    }
}

@main
final class AppDelegate: UIResponder, UIApplicationDelegate {
    var window: UIWindow?
    func application(_ application: UIApplication, didFinishLaunchingWithOptions options: [UIApplication.LaunchOptionsKey: Any]?) -> Bool {
        let window = UIWindow(frame: UIScreen.main.bounds)
        window.rootViewController = FixtureController()
        window.makeKeyAndVisible()
        self.window = window
        return true
    }
}

final class FixtureController: UIViewController, UITextFieldDelegate {
    private let field = WitnessField(frame: .zero)
    private let neighbour = UITextField()
    private let actual = UILabel()
    private let witness = UILabel()
    private let state = UILabel()

    override func viewDidLoad() {
        super.viewDidLoad()
        view.backgroundColor = .systemBackground
        for (input, name) in [(field as UITextField, "field"), (neighbour, "neighbour")] {
            input.accessibilityIdentifier = "proof.\(name)"
            input.borderStyle = .roundedRect
            input.autocorrectionType = .no
            input.autocapitalizationType = .none
            input.addTarget(self, action: #selector(refresh), for: [.editingChanged, .editingDidBegin, .editingDidEnd])
        }
        field.delegate = self
        field.changed = { [weak self] in self?.refresh() }
        actual.accessibilityIdentifier = "proof.actual"
        witness.accessibilityIdentifier = "proof.witness"
        state.accessibilityIdentifier = "proof.state"
        let stack = UIStackView(arrangedSubviews: [field, neighbour, actual, witness, state])
        stack.axis = .vertical
        stack.spacing = 6
        let modes = ["empty", "focusedEmpty", "seed", "focusedSeed", "secure", "focusedSecure", "masked", "focusedMasked", "fallback"]
        for offset in stride(from: 0, to: modes.count, by: 3) {
            let row = UIStackView()
            row.distribution = .fillEqually
            for name in modes[offset..<min(offset + 3, modes.count)] {
                let button = UIButton(type: .system)
                button.setTitle(name, for: .normal)
                button.titleLabel?.font = .systemFont(ofSize: 11)
                button.accessibilityIdentifier = "proof.\(name)"
                button.addAction(UIAction { [weak self] _ in self?.prepare(name) }, for: .touchUpInside)
                row.addArrangedSubview(button)
            }
            stack.addArrangedSubview(row)
        }
        stack.translatesAutoresizingMaskIntoConstraints = false
        view.addSubview(stack)
        NSLayoutConstraint.activate([
            stack.topAnchor.constraint(equalTo: view.safeAreaLayoutGuide.topAnchor, constant: 18),
            stack.centerXAnchor.constraint(equalTo: view.centerXAnchor),
            stack.widthAnchor.constraint(equalToConstant: 340),
            field.heightAnchor.constraint(equalToConstant: 38),
            neighbour.heightAnchor.constraint(equalToConstant: 38),
        ])
        prepare("empty")
    }

    private func prepare(_ mode: String) {
        view.endEditing(true)
        field.isSecureTextEntry = mode.lowercased().contains("secure")
        field.masksAccessibility = mode.lowercased().contains("masked")
        field.refusesSelectionDeletion = mode == "fallback"
        field.selectionDeletionPending = false
        field.text = mode.lowercased().contains("empty") ? "" : "seedvalue"
        neighbour.text = "untouched"
        if mode.hasPrefix("focused") || mode == "fallback" {
            field.becomeFirstResponder()
            field.selectedTextRange = field.textRange(from: field.endOfDocument, to: field.endOfDocument)
        }
        field.taps = 0
        field.selections = 0
        field.rejected = 0
        state.text = "Prepared \(mode)"
        refresh()
    }

    @objc private func refresh() {
        actual.text = "Actual:\(field.text ?? "") Neighbour:\(neighbour.text ?? "")"
        witness.text = "taps=\(field.taps) selections=\(field.selections) rejected=\(field.rejected) targetFocus=\(field.isFirstResponder ? 1 : 0) neighbourFocus=\(neighbour.isFirstResponder ? 1 : 0)"
    }

    func textField(_ textField: UITextField, shouldChangeCharactersIn range: NSRange, replacementString string: String) -> Bool {
        if field.selectionDeletionPending && range.length > 1 && string.isEmpty {
            field.selectionDeletionPending = false
            field.rejected += 1
            field.selectedTextRange = field.textRange(from: field.beginningOfDocument, to: field.beginningOfDocument)
            refresh()
            return false
        }
        return true
    }
}
