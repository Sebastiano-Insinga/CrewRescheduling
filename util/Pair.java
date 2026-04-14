package util;

/**
 * Simple class to store a pair of objects.
 * 
 * @author B.T.C. van Rossum
 *
 * @param <A> class of first object
 * @param <B> class of second object
 */
public class Pair<A, B>
{
	private final A key;
	private final B value;

	/**
	 * Create a pair of a key object and a value object.
	 * 
	 * @param key   key object
	 * @param value value object
	 */
	public Pair(A key, B value)
	{
		this.key = key;
		this.value = value;
	}

	/**
	 * Returns key of the pair.
	 * 
	 * @return key
	 */
	public A getKey()
	{
		return key;
	}

	/**
	 * Returns value of the pair.
	 * 
	 * @return value
	 */
	public B getValue()
	{
		return value;
	}
}
